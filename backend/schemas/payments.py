from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

class PaymentBase(BaseModel):
    purchase_order_id: int
    payment_date: date
    amount_paid: Decimal
    payment_mode: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    payment_receipt: Optional[str] = None

class PaymentCreate(PaymentBase):
    pass

class PaymentUpdate(BaseModel):
    payment_date: Optional[date] = None
    amount_paid: Optional[Decimal] = None
    payment_mode: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    payment_receipt: Optional[str] = None

class Payment(PaymentBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    tenant_id: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    class Config:
        from_attributes = True