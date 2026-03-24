from paddleocr import PaddleOCR
import numpy as np
from PIL import Image
import io
import asyncio
from app.core.logger import logger

# Initialize OCR once (important for performance)
logger.info("Initializing Local PaddleOCR engine...")
ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)

def _sync_ocr_image(image_bytes: bytes) -> str:
    """Run local inference OCR on a single image byte array."""
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_np = np.array(image)

    # Run OCR inference payload
    result = ocr.ocr(img_np)

    extracted_text = []
    if result:
        for res in result:
            if not res: continue
            
            if isinstance(res, dict) and "rec_texts" in res:
                # PaddleOCR 3.3.2+ format (dictionary-based)
                extracted_text.extend(res["rec_texts"])
            elif isinstance(res, list):
                # Legacy or standard list-of-lists format
                for line in res:
                    if isinstance(line, list) and len(line) >= 2:
                        extracted_text.append(line[1][0])

    return "\n".join(extracted_text)

async def extract_text_via_ocr(image_bytes: bytes) -> str:
    """Async wrapper avoiding event-loop blocking on PaddleOCR GPU/CPU calls."""
    try:
        # Offload blocking inference to threadpool
        return await asyncio.to_thread(_sync_ocr_image, image_bytes)
    except Exception as e:
        logger.error(f"Local PaddleOCR extraction failed: {str(e)}")
        return ""
