from fastapi import UploadFile, HTTPException
import PyPDF2
from io import BytesIO

MAX_FILE_SIZE = 5 * 1024 * 1024 # 5 MB

async def process_upload(file: UploadFile) -> str:
    contents = await file.read()
    
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 5MB.")
        
    if file.content_type == "application/pdf":
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(contents))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
            return _sanitize(text)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid PDF file.")
            
    elif file.content_type == "text/plain":
        try:
            text = contents.decode("utf-8")
            return _sanitize(text)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid TXT file.")
            
    else:
        raise HTTPException(status_code=415, detail="Unsupported file format. Only PDF and TXT allowed.")

def _sanitize(text: str) -> str:
    # Strip zero-width and excessive space
    return " ".join(text.split())
