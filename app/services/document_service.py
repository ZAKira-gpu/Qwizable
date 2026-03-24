import fitz
import docx
from io import BytesIO
from typing import List
import re
import asyncio
from app.services.ocr_service import extract_text_via_ocr
from app.core.logger import logger

def clean_and_normalize_text(text: str) -> str:
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def chunk_text(text: str, max_tokens: int = 800) -> List[str]:
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
            current_length += sentence_len + 1
            
    if current_chunk:
        chunks.append(" ".join(current_chunk))
        
    return chunks

async def extract_text_from_file(contents: bytes, filename: str) -> str:
    ext = filename.split('.')[-1].lower()
    
    if ext == 'pdf':
        doc = fitz.open(stream=contents, filetype="pdf")
        page_texts = [""] * len(doc)
        ocr_tasks = []
        
        for i in range(len(doc)):
            page = doc.load_page(i)
            text = page.get_text().strip()
            
            # Fast-path check: If dense text exists, skip OCR completely
            if len(text) < 100:
                pix = page.get_pixmap()
                img_bytes = pix.tobytes("jpeg")
                ocr_tasks.append((i, extract_text_via_ocr(img_bytes)))
            else:
                page_texts[i] = text + " "
                
        # Fire synchronous paddle models via asyncio threadpool mapped to gather
        if ocr_tasks:
            indices = [task[0] for task in ocr_tasks]
            futures = [task[1] for task in ocr_tasks]
            
            results = await asyncio.gather(*futures, return_exceptions=True)
            for idx, res in zip(indices, results):
                if isinstance(res, Exception):
                    logger.error(f"Failed to OCR page {idx}: {res}")
                else:
                    page_texts[idx] = res + " "
                    
        extracted_text = "".join(page_texts)
        
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
