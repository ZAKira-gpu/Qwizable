from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.db.base_class import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    request_type = Column(String, nullable=False) # e.g. 'quiz_generation', 'ai_tutor'
    tokens_used = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
