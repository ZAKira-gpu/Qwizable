from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.payment import Payment
from app.core.logger import logger
from app.services.subscription_service import upgrade_user_plan

async def process_paddle_webhook(db: AsyncSession, alert_name: str, alert_id: str, payload: dict) -> bool:
    existing_event = await db.execute(select(Payment).where(Payment.webhook_id == alert_id))
    if existing_event.scalars().first():
        logger.info(f"Idempotency hit: Webhook {alert_id} already processed. Ignoring.")
        return True 
        
    user_id_str = payload.get("passthrough") or payload.get("custom_data", "")
    if not user_id_str:
        logger.error(f"No user_id in webhook passthrough for webhook {alert_id}")
        return False
        
    try:
        user_id = int(str(user_id_str))
    except ValueError:
        return False

    status = "confirmed" if alert_name in ["subscription_created", "subscription_updated", "payment_succeeded", "subscription_payment_succeeded"] else "failed"

    raw_amount = payload.get("p_price") or payload.get("sale_gross") or payload.get("checkout_gross") or payload.get("amount") or "0.0"
    
    new_payment = Payment(
        user_id=user_id,
        provider="paddle",
        status=status,
        amount=float(raw_amount),
        webhook_id=alert_id
    )
    db.add(new_payment)
    await db.commit()
    
    if status == "confirmed":
        plan_id = payload.get("subscription_plan_id") or "pro"
        await upgrade_user_plan(db, user_id, str(plan_id), alert_id)
        
    return True
