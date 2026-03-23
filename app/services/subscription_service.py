from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.payment import Subscription
from app.models.user import User
from app.utils.payment_status_handler import SubscriptionStatus
from app.core.logger import logger
from datetime import datetime

async def upgrade_user_plan(db: AsyncSession, user_id: int, plan_name: str, webhook_id: str):
    user = await db.get(User, user_id)
    if not user: return False
    user.plan = plan_name
    
    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    sub = result.scalars().first()
    
    if sub:
        sub.plan = plan_name
        sub.status = SubscriptionStatus.ACTIVE.value
    else:
        sub = Subscription(user_id=user_id, plan=plan_name, status=SubscriptionStatus.ACTIVE.value)
        db.add(sub)
        
    await db.commit()
    return True

async def cancel_subscription(db: AsyncSession, user_id: int):
    user = await db.get(User, user_id)
    if user: user.plan = "free"
    
    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    sub = result.scalars().first()
    if sub:
        sub.status = SubscriptionStatus.CANCELED.value
        
    await db.commit()

async def check_expired_subscriptions(db: AsyncSession):
    now = datetime.utcnow()
    query = select(Subscription).where(Subscription.status == SubscriptionStatus.ACTIVE.value).where(Subscription.renew_date < now)
    result = await db.execute(query)
    expired_subs = result.scalars().all()
    
    for sub in expired_subs:
        sub.status = SubscriptionStatus.PAST_DUE.value
        user = await db.get(User, sub.user_id)
        if user:
            user.plan = "free"
            logger.info(f"Downgraded user {user.id} to free due to expired subscription.")
            
    if expired_subs:
        await db.commit()
