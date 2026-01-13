from pydantic import BaseModel, computed_field
from typing import Optional
from datetime import date, datetime
from decimal import Decimal
from utils.formatting import format_indian_currency, amount_to_words

class SalesPaymentBase(BaseModel):
    sales_order_id: int
    payment_date: date
    amount_paid: Decimal
    payment_mode: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    payment_receipt: Optional[str] = None

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
    tenant_id: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    @computed_field
    def amount_paid_str(self) -> str:
        return format_indian_currency(self.amount_paid)

    @computed_field
    def amount_paid_words(self) -> str:
        return amount_to_words(self.amount_paid)

    class Config:
        from_attributes = True