from pydantic import BaseModel
from datetime import date
from typing import List, Optional

# General Ledger
class GeneralLedgerEntry(BaseModel):
    date: date
    transaction_type: str  # E.g., 'Sales Payment', 'Purchase Payment', 'Operational Expense'
    party: str             # E.g., 'Customer Name', 'Vendor Name'
    reference_document: Optional[str] = None # E.g., 'SO-13', 'PO-25'
    details: str           # A more descriptive text about the transaction
    debit: float = 0.0
    credit: float = 0.0
    balance: float

class GeneralLedger(BaseModel):
    title: str
    opening_balance: float
    entries: List[GeneralLedgerEntry]
    closing_balance: float

# Subsidiary Ledger - Purchases
class PurchaseLedgerEntry(BaseModel):
    date: date
    vendor_name: str
    invoice_number: str
    description: Optional[str] = None
    amount: float
    amount_paid: float
    balance_amount: float
    payment_status: str

class PurchaseLedger(BaseModel):
    title: str
    vendor_id: int
    entries: List[PurchaseLedgerEntry]

# Subsidiary Ledger - Sales
class SalesLedgerEntry(BaseModel):
    date: date
    customer_name: str
    invoice_number: str
    description: Optional[str] = None
    amount: float
    amount_paid: float
    balance_amount: float
    payment_status: str

class SalesLedger(BaseModel):
    title: str
    customer_id: int
    entries: List[SalesLedgerEntry]

# Subsidiary Ledger - Inventory
class InventoryLedgerEntry(BaseModel):
    date: date
    reference: str # Purchase ID or Sales ID
    quantity_received: Optional[float] = None
    unit_cost: Optional[float] = None
    total_cost: Optional[float] = None
    quantity_sold: Optional[float] = None
    quantity_on_hand: float

class InventoryLedger(BaseModel):
    title: str
    item_id: int
    opening_quantity: float
    entries: List[InventoryLedgerEntry]
    closing_quantity_on_hand: float
