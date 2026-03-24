from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.sql import func
from app.db.base_class import Base

class Usage(Base):
    __tablename__ = "usages"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    tokens_used = Column(Integer, default=0)
    quizzes_generated = Column(Integer, default=0)
    docs_uploaded = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
