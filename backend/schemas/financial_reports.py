from pydantic import BaseModel, computed_field
from decimal import Decimal
from utils.formatting import format_indian_currency, amount_to_words

class ProfitAndLoss(BaseModel):
    revenue: Decimal
    cogs: Decimal
    gross_profit: Decimal
    operating_expenses: Decimal
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

BalanceSheet.model_rebuild()
