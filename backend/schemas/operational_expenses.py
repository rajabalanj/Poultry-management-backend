from pydantic import BaseModel, computed_field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from utils.formatting import format_indian_currency, amount_to_words

class OperationalExpenseBase(BaseModel):
    expense_date: date
    account_id: Optional[int] = None
    amount: Decimal

class OperationalExpenseCreate(OperationalExpenseBase):
    pass

class OperationalExpenseUpdate(BaseModel):
    expense_date: Optional[date] = None
    account_id: Optional[int] = None
    amount: Optional[Decimal] = None

class OperationalExpense(OperationalExpenseBase):
    id: int
    tenant_id: str
    account_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    @computed_field
    def amount_str(self) -> str:
        return format_indian_currency(self.amount)

    @computed_field
    def amount_words(self) -> str:
        return amount_to_words(self.amount)

    class Config:
        from_attributes = True
