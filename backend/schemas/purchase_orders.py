from pydantic import BaseModel, computed_field
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from models.purchase_orders import PurchaseOrderStatus # Import the enum
from schemas.purchase_order_items import PurchaseOrderItemCreateRequest
from utils.formatting import format_indian_currency, amount_to_words

# Forward declaration for recursive models
class PurchaseOrderItem(BaseModel): # Defined below properly, but needed for List type hint
    id: int
    inventory_item_id: int
    quantity: Decimal
    price_per_unit: Decimal
    line_total: Decimal
    tenant_id: Optional[str] = None

    @computed_field
    def price_per_unit_str(self) -> str:
        return format_indian_currency(self.price_per_unit)

    @computed_field
    def price_per_unit_words(self) -> str:
        return amount_to_words(self.price_per_unit)

    @computed_field
    def line_total_str(self) -> str:
        return format_indian_currency(self.line_total)

    @computed_field
    def line_total_words(self) -> str:
        return amount_to_words(self.line_total)

    class Config:
        from_attributes = True

class Payment(BaseModel): # Defined below properly, but needed for List type hint
    id: int
    payment_date: date
    amount_paid: Decimal
    payment_mode: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    payment_receipt: Optional[str] = None
    tenant_id: Optional[str] = None

    @computed_field
    def amount_paid_str(self) -> str:
        return format_indian_currency(self.amount_paid)

    @computed_field
    def amount_paid_words(self) -> str:
        return amount_to_words(self.amount_paid)

    class Config:
        from_attributes = True

class PurchaseOrderBase(BaseModel):
    vendor_id: int  # Now references business_partners table
    order_date: date
    status: Optional[PurchaseOrderStatus] = PurchaseOrderStatus.DRAFT
    notes: Optional[str] = None
    payment_receipt: Optional[str] = None
    bill_no: Optional[str] = None

class PurchaseOrderCreate(PurchaseOrderBase):
    # When creating, items are often part of the initial request
    items: List[PurchaseOrderItemCreateRequest] # List of items to be included in this PO

class PurchaseOrderUpdate(BaseModel):
    vendor_id: Optional[int] = None
    order_date: Optional[date] = None
    status: Optional[PurchaseOrderStatus] = None
    notes: Optional[str] = None
    payment_receipt: Optional[str] = None
    bill_no: Optional[str] = None
    # Items updates are typically handled via separate endpoints (add/remove item from PO)
    # total_amount is system-calculated, not updated directly

class PurchaseOrder(PurchaseOrderBase):
    id: int
    po_number: Optional[int] = None
    tenant_id: Optional[str] = None
    total_amount: Decimal
    total_amount_paid: Decimal
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    bill_no: Optional[str] = None
    # Include related items and payments for detailed view
    items: List['PurchaseOrderItem'] = []
    payments: List['Payment'] = []

    @computed_field
    def total_amount_str(self) -> str:
        return format_indian_currency(self.total_amount)

    @computed_field
    def total_amount_words(self) -> str:
        return amount_to_words(self.total_amount)

    @computed_field
    def total_amount_paid_str(self) -> str:
        return format_indian_currency(self.total_amount_paid)

    @computed_field
    def total_amount_paid_words(self) -> str:
        return amount_to_words(self.total_amount_paid)

    class Config:
        from_attributes = True