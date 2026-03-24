import fitz # PyMuPDF
import docx
from io import BytesIO
from typing import List
import re
from app.services.ocr_service import extract_text_via_ocr

def clean_and_normalize_text(text: str) -> str:
    """Removes noise, normalizes whitespace, fixes line breaks."""
    text = re.sub(r'[^\x00-\x7F]+', ' ', text) # Remove non-ASCII
    text = re.sub(r'\s+', ' ', text) # Normalize whitespace
    return text.strip()

def chunk_text(text: str, max_tokens: int = 800) -> List[str]:
    """
    Split large documents into smaller chunks for efficient LLM processing.
    Assumes ~4 characters per token. Avoids cutting sentences mid-way.
    """
    max_chars = max_tokens * 4
    sentences = re.split(r'(?<=[.!?]) +', text)
    
    chunks = []
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence: continue
        
        sentence_len = len(sentence)
        if current_length + sentence_len > max_chars and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_length = sentence_len
        else:
            current_chunk.append(sentence)
            current_length += sentence_len + 1 # +1 for space
            
    if current_chunk:
        chunks.append(" ".join(current_chunk))
        
    return chunks

async def extract_text_from_file(contents: bytes, filename: str) -> str:
    """Routes file to correct parser by extension."""
    ext = filename.split('.')[-1].lower()
    extracted_text = ""
    
    if ext == 'pdf':
        doc = fitz.open(stream=contents, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text().strip()
            
            # If page has almost no text, assume it's scanned and send to OCR
            if len(text) < 50:
                pix = page.get_pixmap()
                img_bytes = pix.tobytes("jpeg")
                ocr_text = await extract_text_via_ocr(img_bytes)
                extracted_text += ocr_text + " "
            else:
                extracted_text += text + " "
    elif ext in ['docx', 'doc']:
        doc = docx.Document(BytesIO(contents))
        extracted_text = " ".join([p.text for p in doc.paragraphs])
    elif ext in ['md', 'txt']:
        extracted_text = contents.decode('utf-8', errors='ignore')
    elif ext in ['jpg', 'jpeg', 'png']:
        extracted_text = await extract_text_via_ocr(contents)
    else:
        raise ValueError(f"Unsupported file type: {ext}")
        
    return clean_and_normalize_text(extracted_text)
