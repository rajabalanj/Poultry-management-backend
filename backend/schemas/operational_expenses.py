from pydantic import BaseModel
from datetime import date
from decimal import Decimal
from typing import Optional

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

    class Config:
        from_attributes = True
