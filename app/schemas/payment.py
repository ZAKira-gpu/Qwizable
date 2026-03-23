from typing import Any, Dict
from pydantic import BaseModel

class PaddleWebhook(BaseModel):
    alert_name: str
    alert_id: str
    payload: Dict[str, Any]

class CheckoutSessionRequest(BaseModel):
    plan_id: str
