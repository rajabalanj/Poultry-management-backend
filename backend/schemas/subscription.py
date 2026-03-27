from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

class SubscriptionBase(BaseModel):
    is_paid: bool = False
    payment_date: Optional[date] = None
    notes: Optional[str] = None

class SubscriptionCreate(SubscriptionBase):
    tenant_id: str

class SubscriptionUpdate(BaseModel):
    is_paid: Optional[bool] = None
    payment_date: Optional[date] = None
    notes: Optional[str] = None

class Subscription(SubscriptionBase):
    id: int
    tenant_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
