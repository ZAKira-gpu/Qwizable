from paddleocr import PaddleOCR
import numpy as np
from PIL import Image
import io
import asyncio
from app.core.logger import logger

logger.info("Initializing Local PaddleOCR engine...")
ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)

def resize_image(image: Image.Image, max_size=1024) -> Image.Image:
    """Scales down massive images to save VRAM and OCR times."""
    image.thumbnail((max_size, max_size))
    return image

def _sync_ocr_image(image_bytes: bytes) -> str:
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image = resize_image(image)
        img_np = np.array(image)

        result = ocr.ocr(img_np)

        extracted_text = []
        if result:
            for res in result:
                if not res: continue
                if isinstance(res, dict) and "rec_texts" in res:
                    extracted_text.extend(res["rec_texts"])
                elif isinstance(res, list):
                    for line in res:
                        if isinstance(line, list) and len(line) >= 2:
                            extracted_text.append(line[1][0])

        return "\n".join(extracted_text)
    except Exception as e:
        logger.error(f"Sync OCR Pipeline Failure: {e}")
        return ""

async def extract_text_via_ocr(image_bytes: bytes) -> str:
    try:
        return await asyncio.to_thread(_sync_ocr_image, image_bytes)
    except Exception as e:
        logger.error(f"Async PaddleOCR threadoff failed: {str(e)}")
        return ""
