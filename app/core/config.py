import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Qwizable"
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"
    
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    DATABASE_URL: str
    REDIS_URL: str
    
    NOVITA_API_KEY: str
    PADDLE_API_KEY: str
    PADDLE_WEBHOOK_SECRET: str
    COINREMITTER_API_KEY: str
    COINREMITTER_PASSWORD: str
    
    # Feature Flags
    FEATURES: Dict[str, bool] = {
        "coding_mode": False,
        "ai_tutor": True
    }

    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE", ".env.dev"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
