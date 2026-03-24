import base64
import httpx
from app.core.config import settings
from app.core.logger import logger
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

class OCRError(Exception):
    pass

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException, OCRError))
)
async def extract_text_via_ocr(image_bytes: bytes) -> str:
    """
    Uses ERNIE 4.5 VL API to extract text and visual context together natively, 
    preserving multi-modal contextual layout from mixed diagrams.
    """
    if not settings.NOVITA_API_KEY:
        logger.warning("NOVITA_API_KEY missing - Vision extraction disabled.")
        return ""
        
    b64_image = base64.b64encode(image_bytes).decode('utf-8')
    data_uri = f"data:image/jpeg;base64,{b64_image}"
    
    headers = {
        "Authorization": f"Bearer {settings.NOVITA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "ernie-4.5-vl", 
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract all readable text, and describe any visual diagrams or charts in detail. Return only the extracted and described information cleanly."},
                    {"type": "image_url", "image_url": {"url": data_uri}}
                ]
            }
        ],
        "max_tokens": 1500,
        "temperature": 0.1
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                "https://api.novita.ai/v3/openai/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"].strip()
            raise OCRError("Invalid ERNIE 4.5 VL response format.")
        except httpx.HTTPStatusError as e:
            logger.error(f"Vision API HTTP Error {e.response.status_code}: {e.response.text}")
            raise OCRError(f"Vision Failed with status {e.response.status_code}")
