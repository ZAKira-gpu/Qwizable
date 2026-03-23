from sqlalchemy import Column, Integer, String, ForeignKey, Float, JSON
from app.db.base_class import Base

class Result(Base):
    __tablename__ = "results"
    
    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), index=True, nullable=False)
    score = Column(Float, nullable=False)
    weak_areas = Column(JSON, nullable=False)
    feedback = Column(String, nullable=False)
