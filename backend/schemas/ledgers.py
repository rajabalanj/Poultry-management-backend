from pydantic import BaseModel, computed_field
from datetime import date
from typing import List, Optional
from decimal import Decimal
from utils.formatting import format_indian_currency, amount_to_words

# General Ledger
class GeneralLedgerEntry(BaseModel):
    date: date
    transaction_type: str
    party: str
    reference_document: Optional[str] = None
    transaction_id: Optional[int] = None  # ID of the payment (SP or PP)
    reference_id: Optional[int] = None      # ID of the SO or PO
    details: str
    debit: Decimal = Decimal('0.0')
    credit: Decimal = Decimal('0.0')
    balance: Decimal

    @computed_field
    def debit_str(self) -> str:
        return format_indian_currency(self.debit)

    @computed_field
    def debit_words(self) -> str:
        return amount_to_words(self.debit)

    @computed_field
    def credit_str(self) -> str:
        return format_indian_currency(self.credit)

    @computed_field
    def credit_words(self) -> str:
        return amount_to_words(self.credit)

    @computed_field
    def balance_str(self) -> str:
        return format_indian_currency(self.balance)

    @computed_field
    def balance_words(self) -> str:
        return amount_to_words(self.balance)

class GeneralLedger(BaseModel):
    title: str
    opening_balance: Decimal
    entries: List[GeneralLedgerEntry]
    closing_balance: Decimal

    @computed_field
    def opening_balance_str(self) -> str:
        return format_indian_currency(self.opening_balance)

    @computed_field
    def opening_balance_words(self) -> str:
        return amount_to_words(self.opening_balance)

    @computed_field
    def closing_balance_str(self) -> str:
        return format_indian_currency(self.closing_balance)

    @computed_field
    def closing_balance_words(self) -> str:
        return amount_to_words(self.closing_balance)

# Subsidiary Ledger - Purchases
class PurchaseLedgerEntry(BaseModel):
    date: date
    vendor_name: str
    po_id: Optional[int] = None
    invoice_number: str
    description: Optional[str] = None
    amount: Decimal
    amount_paid: Decimal
    balance_amount: Decimal
    payment_status: str

    @computed_field
    def amount_str(self) -> str:
        return format_indian_currency(self.amount)

    @computed_field
    def amount_words(self) -> str:
        return amount_to_words(self.amount)

    @computed_field
    def amount_paid_str(self) -> str:
        return format_indian_currency(self.amount_paid)

    @computed_field
    def amount_paid_words(self) -> str:
        return amount_to_words(self.amount_paid)

    @computed_field
    def balance_amount_str(self) -> str:
        return format_indian_currency(self.balance_amount)

    @computed_field
    def balance_amount_words(self) -> str:
        return amount_to_words(self.balance_amount)

class PurchaseLedger(BaseModel):
    title: str
    vendor_id: int
    entries: List[PurchaseLedgerEntry]

# Subsidiary Ledger - Sales
class SalesLedgerEntry(BaseModel):
    date: date
    customer_name: str
    so_id: Optional[int] = None
    invoice_number: str
    description: Optional[str] = None
    amount: Decimal
    amount_paid: Decimal
    balance_amount: Decimal
    payment_status: str

    @computed_field
    def amount_str(self) -> str:
        return format_indian_currency(self.amount)

    @computed_field
    def amount_words(self) -> str:
        return amount_to_words(self.amount)

    @computed_field
    def amount_paid_str(self) -> str:
        return format_indian_currency(self.amount_paid)

    @computed_field
    def amount_paid_words(self) -> str:
        return amount_to_words(self.amount_paid)

    @computed_field
    def balance_amount_str(self) -> str:
        return format_indian_currency(self.balance_amount)

    @computed_field
    def balance_amount_words(self) -> str:
        return amount_to_words(self.balance_amount)

class SalesLedger(BaseModel):
    title: str
    customer_id: int
    entries: List[SalesLedgerEntry]

# Subsidiary Ledger - Inventory
class InventoryLedgerEntry(BaseModel):
    date: date
    reference: str # Purchase ID or Sales ID
    quantity_received: Optional[Decimal] = None
    unit_cost: Optional[Decimal] = None
    total_cost: Optional[Decimal] = None
    quantity_sold: Optional[Decimal] = None
    quantity_on_hand: Decimal

    @computed_field
    def unit_cost_str(self) -> str:
        return format_indian_currency(self.unit_cost)

    @computed_field
    def unit_cost_words(self) -> str:
        return amount_to_words(self.unit_cost)

    @computed_field
    def total_cost_str(self) -> str:
        return format_indian_currency(self.total_cost)

    @computed_field
    def total_cost_words(self) -> str:
        return amount_to_words(self.total_cost)

class InventoryLedger(BaseModel):
    title: str
    item_id: int
    opening_quantity: Decimal
    entries: List[InventoryLedgerEntry]
    closing_quantity_on_hand: Decimal
