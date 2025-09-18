from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

class SalesPaymentBase(BaseModel):
    sales_order_id: int
    payment_date: date
    amount_paid: Decimal
    payment_mode: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    payment_receipt: Optional[str] = None
    tenant_id: Optional[str] = None

class SalesPaymentCreate(SalesPaymentBase):
    pass

class SalesPaymentUpdate(BaseModel):
    payment_date: Optional[date] = None
    amount_paid: Optional[Decimal] = None
    payment_mode: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    payment_receipt: Optional[str] = None

class SalesPayment(SalesPaymentBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True