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

    # Paddle Classic: passthrough is a plain string user_id
    # Paddle V2: custom_data is a dict {"user_id": 42}
    user_id_str = payload.get("passthrough")
    if not user_id_str:
        custom_data = payload.get("custom_data")
        if isinstance(custom_data, dict):
            user_id_str = custom_data.get("user_id")
        elif isinstance(custom_data, str):
            user_id_str = custom_data

    if not user_id_str:
        logger.error(f"No user_id in webhook passthrough for webhook {alert_id}")
        return False
        
    try:
        user_id = int(str(user_id_str))
    except ValueError:
        return False

    # Support both Paddle Classic and V2 event names
    SUCCESS_EVENTS = {
        "subscription_created", "subscription_updated",
        "payment_succeeded", "subscription_payment_succeeded",
        # Paddle Billing V2 event types:
        "subscription.created", "subscription.updated",
        "transaction.completed", "transaction.paid",
    }
    status = "confirmed" if alert_name in SUCCESS_EVENTS else "failed"

    raw_amount = (
        payload.get("p_price") or payload.get("sale_gross") or
        payload.get("checkout_gross") or payload.get("amount") or
        payload.get("details", {}).get("totals", {}).get("grand_total") or "0.0"
    )
    
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
        plan_id = payload.get("subscription_plan_id") or payload.get("product_id") or "pro"
        await upgrade_user_plan(db, user_id, str(plan_id), alert_id)
        
    return True

