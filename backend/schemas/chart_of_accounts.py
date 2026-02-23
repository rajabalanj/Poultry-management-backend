
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime

VALID_ACCOUNT_TYPES = ["Asset", "Liability", "Equity", "Revenue", "Expense"]

class ChartOfAccountsBase(BaseModel):
    account_code: str
    account_name: str
    account_type: str  # Asset, Liability, Equity, Revenue, Expense
    description: Optional[str] = None
    is_active: bool = True

    @field_validator('account_type')
    @classmethod
    def validate_account_type(cls, v):
        if v not in VALID_ACCOUNT_TYPES:
            raise ValueError(f"account_type must be one of {VALID_ACCOUNT_TYPES}")
        return v

class ChartOfAccountsCreate(ChartOfAccountsBase):
    pass

class ChartOfAccountsUpdate(BaseModel):
    account_name: Optional[str] = None
    account_type: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class ChartOfAccounts(ChartOfAccountsBase):
    id: int
    tenant_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
