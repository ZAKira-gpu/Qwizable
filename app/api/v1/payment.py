from fastapi import APIRouter, Depends, Request, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.payment import PaddleWebhook
from app.services.payment_service import process_paddle_webhook
import hmac
import hashlib
from app.core.config import settings

router = APIRouter()

def verify_paddle_signature(signature: str, payload_str: str, secret: str) -> bool:
    if not signature or not secret: return False
    expected_hmac = hmac.new(
        secret.encode('utf-8'),
        payload_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_hmac)

@router.post("/webhook/paddle")
async def paddle_webhook(
    request: Request,
    paddle_signature: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    body = await request.body()
    if not verify_paddle_signature(paddle_signature, body.decode(), settings.PADDLE_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
    import json
    try:
        payload_data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
        
    alert_name = payload_data.get("alert_name", "unknown")
    alert_id = payload_data.get("alert_id", "unknown")
    payload = payload_data.get("payload", {})
    
    success = await process_paddle_webhook(db, alert_name, alert_id, payload)
    if not success:
        return {"success": False, "data": None, "error": "Webhook processing failed"}
    return {"success": True, "data": {"status": "ok"}, "error": None}
