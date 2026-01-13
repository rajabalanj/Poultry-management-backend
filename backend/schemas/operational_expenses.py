from pydantic import BaseModel, computed_field
from datetime import date
from decimal import Decimal
from typing import Optional
from utils.formatting import format_indian_currency, amount_to_words

class OperationalExpenseBase(BaseModel):
    date: date
    expense_type: str
    amount: Decimal

class OperationalExpenseCreate(OperationalExpenseBase):
    pass

class OperationalExpenseUpdate(OperationalExpenseBase):
    pass

class OperationalExpense(OperationalExpenseBase):
    id: int
    tenant_id: str
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
