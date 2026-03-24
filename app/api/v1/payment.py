from fastapi import APIRouter, Depends, Request, HTTPException, Form, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.payment_service import process_paddle_webhook
from app.core.rate_limit import rate_limiter
from app.core.config import settings
import base64
import hmac
import hashlib
import json
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
    db: AsyncSession = Depends(get_db),
    _=Depends(rate_limiter.check_ip_limit)
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

def verify_paddle_v2_hmac(signature: str, payload_str: str, secret: str) -> bool:
    if not signature or not secret: return False
    
    # Paddle V2 sends "ts=1234;h1=abcd". We need to extract the hash.
    try:
        parts = {p.split('=')[0]: p.split('=')[1] for p in signature.split(';')}
        ts = parts.get('ts')
        h1 = parts.get('h1')
        
        if not ts or not h1:
            return False
            
        signed_payload = f"{ts}:{payload_str}"
        expected_hmac = hmac.new(
            secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(h1, expected_hmac)
    except Exception:
        return False

@router.post("/webhook/paddle/v2")
async def paddle_webhook_v2(
    request: Request,
    paddle_signature: str = Header(None, alias="Paddle-Signature"),
    db: AsyncSession = Depends(get_db),
    _=Depends(rate_limiter.check_ip_limit)
):
    if not verify_paddle_ip(request.client.host) and os.getenv("ENVIRONMENT") == "production":
        raise HTTPException(status_code=403, detail="Unauthorized IP.")
        
    body = await request.body()
    body_str = body.decode('utf-8')
    
    if not verify_paddle_v2_hmac(paddle_signature, body_str, settings.PADDLE_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid V2 webhook signature")
        
    try:
        payload_data = json.loads(body_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
        
    event_type = payload_data.get("event_type", "unknown")
    event_id = payload_data.get("event_id", "unknown")
    data_block = payload_data.get("data", {})
    
    success = await process_paddle_webhook(db, event_type, event_id, data_block)
    if not success:
         raise HTTPException(status_code=500, detail="V2 Processing failed")
         
    return {"success": True, "data": {"status": "ok"}, "error": None}
