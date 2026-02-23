from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class FinancialSettingsBase(BaseModel):
    default_cash_account_id: Optional[int] = None
    default_sales_account_id: Optional[int] = None
    default_inventory_account_id: Optional[int] = None
    default_cogs_account_id: Optional[int] = None
    default_operational_expense_account_id: Optional[int] = None
    default_accounts_payable_account_id: Optional[int] = None
    default_accounts_receivable_account_id: Optional[int] = None
    

class FinancialSettingsCreate(FinancialSettingsBase):
    pass

class FinancialSettingsUpdate(FinancialSettingsBase):
    pass

class FinancialSettings(FinancialSettingsBase):
    tenant_id: str
    class Config:
        from_attributes = True