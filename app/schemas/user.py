from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr
    plan: Optional[str] = "free"

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class UsageResponse(BaseModel):
    quizzes_generated: int
    tokens_used: int
    soft_limit_warning: bool = False
