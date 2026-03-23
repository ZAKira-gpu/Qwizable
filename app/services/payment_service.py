from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.payment import Payment
from app.core.logger import logger
from app.services.subscription_service import upgrade_user_plan

async def process_paddle_webhook(db: AsyncSession, alert_name: str, alert_id: str, payload: dict) -> bool:
    # 1. Idempotency Check
    existing_event = await db.execute(select(Payment).where(Payment.webhook_id == alert_id))
    if existing_event.scalars().first():
        logger.info(f"Idempotency hit: Webhook {alert_id} already processed. Ignoring.")
        return True # Acknowledge the retry but do no work
        
    user_id_str = payload.get("passthrough")
    if not user_id_str:
        logger.error("No user_id in webhook passthrough")
        return False
        
    try:
        user_id = int(user_id_str)
    except ValueError:
        return False

    status = "confirmed" if alert_name in ["subscription_created", "subscription_updated"] else "failed"

    new_payment = Payment(
        user_id=user_id,
        provider="paddle",
        status=status,
        amount=float(payload.get("amount", 0.0)),
        webhook_id=alert_id
    )
    db.add(new_payment)
    await db.commit()
    
    if status == "confirmed":
        await upgrade_user_plan(db, user_id, "pro", alert_id)
        
    return True
