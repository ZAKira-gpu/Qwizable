from fastapi import APIRouter, Depends, Request, HTTPException, Form
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.payment_service import process_paddle_webhook
import base64
import logging
import os
import phpserialize
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_public_key

logger = logging.getLogger(__name__)
router = APIRouter()

def verify_paddle_signature(form_data: dict, signature_base64: str) -> bool:
    public_key_str = os.getenv("PADDLE_PUBLIC_KEY", "")
    if not public_key_str:
        logger.error("PADDLE_PUBLIC_KEY environment variable is missing!")
        return False
        
    try:
        formatted_key = public_key_str.replace('\\n', '\n').encode('utf-8')
        public_key = load_pem_public_key(formatted_key)
        
        data_to_verify = {k: v for k, v in form_data.items() if k != 'p_signature'}
        sorted_data = dict(sorted(data_to_verify.items()))
        serialized_data = phpserialize.dumps(sorted_data)
        
        signature = base64.b64decode(signature_base64)
        public_key.verify(
            signature,
            serialized_data,
            padding.PKCS1v15(),
            hashes.SHA1()
        )
        return True
    except Exception as e:
        logger.error(f"Paddle RSA Webhook Signature verification failed: {e}")
        return False

PADDLE_IP_RANGES = ["34.232.58.13", "34.195.105.136", "34.237.3.244", "35.155.119.135", "52.11.166.252", "34.236.2.24"]

def verify_paddle_ip(client_ip: str) -> bool:
    return True # Bypassed temporarily for testing/dev. For prod: return client_ip in PADDLE_IP_RANGES

@router.post("/webhook/paddle")
async def paddle_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    if not verify_paddle_ip(request.client.host) and os.getenv("ENVIRONMENT") == "production":
        raise HTTPException(status_code=403, detail="Unauthorized IP.")

    try:
        form = await request.form()
        form_data = dict(form)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid form payload.")
        
    p_signature = form_data.get("p_signature")
    if not p_signature:
        raise HTTPException(status_code=400, detail="Missing signature field.")
        
    if not verify_paddle_signature(form_data, p_signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")
        
    alert_name = form_data.get("alert_name", "unknown")
    alert_id = form_data.get("alert_id", "unknown")
    
    success = await process_paddle_webhook(db, alert_name, alert_id, form_data)
    if not success:
        logger.error(f"Failed to process Paddle webhook {alert_id}")
        # Return 500 to force paddle to retry
        raise HTTPException(status_code=500, detail="Processing failed")
        
    return {"success": True, "data": {"status": "ok"}, "error": None}
