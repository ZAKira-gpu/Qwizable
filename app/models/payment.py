from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float
from sqlalchemy.sql import func
from app.db.base_class import Base

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    provider = Column(String, nullable=False) # 'paddle' or 'coinremitter'
    status = Column(String, nullable=False) # 'pending', 'confirmed', 'failed'
    amount = Column(Float, nullable=False)
    webhook_id = Column(String, unique=True, index=True, nullable=True) # IDEMPOTENCY
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    plan = Column(String, nullable=False)
    status = Column(String, nullable=False) # 'active', 'canceled'
    renew_date = Column(DateTime(timezone=True), nullable=True)
