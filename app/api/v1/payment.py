from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.payment import PaddleWebhook
from app.services.payment_service import process_paddle_webhook

router = APIRouter()

@router.post("/webhook/paddle")
async def paddle_webhook(
    payload: PaddleWebhook,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    success = await process_paddle_webhook(db, payload.alert_name, payload.alert_id, payload.payload)
    if not success:
        raise HTTPException(status_code=400, detail="Webhook processing failed")
    return {"status": "ok"}
