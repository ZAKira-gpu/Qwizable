from enum import Enum

class PaymentStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"

class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"

def can_transition(current: str, target: str) -> bool:
    if current == PaymentStatus.CONFIRMED:
        return False
    if current == PaymentStatus.FAILED:
        return target == PaymentStatus.PENDING
        
    if current == SubscriptionStatus.CANCELED:
        return target == SubscriptionStatus.ACTIVE
    return True
