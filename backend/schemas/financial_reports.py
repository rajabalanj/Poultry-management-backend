from pydantic import BaseModel, computed_field
from decimal import Decimal
from utils.formatting import format_indian_currency, amount_to_words
from typing import Optional

class ExpenseByAccount(BaseModel):
    account_code: Optional[str]
    account_name: Optional[str]
    amount: Decimal

    @computed_field
    def amount_str(self) -> str:
        return format_indian_currency(self.amount)

    @computed_field
    def amount_words(self) -> str:
        return amount_to_words(self.amount)

class ProfitAndLoss(BaseModel):
    revenue: Decimal
    cogs: Decimal
    gross_profit: Decimal
    operating_expenses: Decimal
    operating_expenses_by_account: list[ExpenseByAccount] = []
    net_income: Decimal

    @computed_field
    def revenue_str(self) -> str:
        return format_indian_currency(self.revenue)

    @computed_field
    def revenue_words(self) -> str:
        return amount_to_words(self.revenue)

    @computed_field
    def cogs_str(self) -> str:
        return format_indian_currency(self.cogs)

    @computed_field
    def cogs_words(self) -> str:
        return amount_to_words(self.cogs)

    @computed_field
    def gross_profit_str(self) -> str:
        return format_indian_currency(self.gross_profit)

    @computed_field
    def gross_profit_words(self) -> str:
        return amount_to_words(self.gross_profit)

    @computed_field
    def operating_expenses_str(self) -> str:
        return format_indian_currency(self.operating_expenses)

    @computed_field
    def operating_expenses_words(self) -> str:
        return amount_to_words(self.operating_expenses)

    @computed_field
    def net_income_str(self) -> str:
        return format_indian_currency(self.net_income)

    @computed_field
    def net_income_words(self) -> str:
        return amount_to_words(self.net_income)

class BalanceSheet(BaseModel):
    assets: 'Assets'
    liabilities: 'Liabilities'
    equity: Decimal

    @computed_field
    def equity_str(self) -> str:
        return format_indian_currency(self.equity)

    @computed_field
    def equity_words(self) -> str:
        return amount_to_words(self.equity)

class Assets(BaseModel):
    current_assets: 'CurrentAssets'

class CurrentAssets(BaseModel):
    cash: Decimal
    accounts_receivable: Decimal
    inventory: Decimal

    @computed_field
    def cash_str(self) -> str:
        return format_indian_currency(self.cash)

    @computed_field
    def cash_words(self) -> str:
        return amount_to_words(self.cash)

    @computed_field
    def accounts_receivable_str(self) -> str:
        return format_indian_currency(self.accounts_receivable)

    @computed_field
    def accounts_receivable_words(self) -> str:
        return amount_to_words(self.accounts_receivable)

    @computed_field
    def inventory_str(self) -> str:
        return format_indian_currency(self.inventory)

    @computed_field
    def inventory_words(self) -> str:
        return amount_to_words(self.inventory)

class Liabilities(BaseModel):
    current_liabilities: 'CurrentLiabilities'

class CurrentLiabilities(BaseModel):
    accounts_payable: Decimal

    @computed_field
    def accounts_payable_str(self) -> str:
        return format_indian_currency(self.accounts_payable)

    @computed_field
    def accounts_payable_words(self) -> str:
        return amount_to_words(self.accounts_payable)

class FinancialSummary(BaseModel):
    eggs_produced: int
    eggs_sold: int
    cost_per_egg: Decimal
    selling_price_per_egg: Decimal
    net_margin_per_egg: Decimal
    cash_balance: Decimal
    receivables: Decimal
    payables: Decimal

    @computed_field
    def cost_per_egg_str(self) -> str:
        return format_indian_currency(self.cost_per_egg)

    @computed_field
    def selling_price_per_egg_str(self) -> str:
        return format_indian_currency(self.selling_price_per_egg)

    @computed_field
    def net_margin_per_egg_str(self) -> str:
        return format_indian_currency(self.net_margin_per_egg)

    @computed_field
    def cash_balance_str(self) -> str:
        return format_indian_currency(self.cash_balance)
    
    @computed_field
    def cash_balance_words(self) -> str:
        return amount_to_words(self.cash_balance)

    @computed_field
    def receivables_str(self) -> str:
        return format_indian_currency(self.receivables)

    @computed_field
    def receivables_words(self) -> str:
        return amount_to_words(self.receivables)

    @computed_field
    def payables_str(self) -> str:
        return format_indian_currency(self.payables)

    @computed_field
    def payables_words(self) -> str:
        return amount_to_words(self.payables)

BalanceSheet.model_rebuild()
