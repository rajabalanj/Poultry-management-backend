from pydantic import BaseModel
from datetime import date
from decimal import Decimal

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

    class Config:
        from_attributes = True
