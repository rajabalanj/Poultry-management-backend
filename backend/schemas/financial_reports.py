from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal

class ProfitAndLoss(BaseModel):
    revenue: Decimal
    cogs: Decimal
    gross_profit: Decimal
    operating_expenses: Decimal
    net_income: Decimal

class BalanceSheet(BaseModel):
    assets: 'Assets'
    liabilities: 'Liabilities'
    equity: Decimal

class Assets(BaseModel):
    current_assets: 'CurrentAssets'

class CurrentAssets(BaseModel):
    cash: Decimal
    accounts_receivable: Decimal
    inventory: Decimal

class Liabilities(BaseModel):
    current_liabilities: 'CurrentLiabilities'

class CurrentLiabilities(BaseModel):
    accounts_payable: Decimal

BalanceSheet.model_rebuild()
