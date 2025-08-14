from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from models.purchase_orders import PurchaseOrderStatus # Import the enum
from schemas.purchase_order_items import PurchaseOrderItemCreateRequest

# Forward declaration for recursive models
class PurchaseOrderItem(BaseModel): # Defined below properly, but needed for List type hint
    id: int
    inventory_item_id: int
    quantity: Decimal
    price_per_unit: Decimal
    line_total: Decimal

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

    class Config:
        from_attributes = True

class PurchaseOrderBase(BaseModel):
    vendor_id: int
    order_date: date
    status: Optional[PurchaseOrderStatus] = PurchaseOrderStatus.DRAFT
    notes: Optional[str] = None
    payment_receipt: Optional[str] = None

class PurchaseOrderCreate(PurchaseOrderBase):
    # When creating, items are often part of the initial request
    items: List[PurchaseOrderItemCreateRequest] # List of items to be included in this PO

class PurchaseOrderUpdate(BaseModel):
    vendor_id: Optional[int] = None
    order_date: Optional[date] = None
    status: Optional[PurchaseOrderStatus] = None
    notes: Optional[str] = None
    payment_receipt: Optional[str] = None
    # Items updates are typically handled via separate endpoints (add/remove item from PO)
    # total_amount is system-calculated, not updated directly

class PurchaseOrder(PurchaseOrderBase):
    id: int
    total_amount: Decimal
    total_amount_paid: Decimal
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    # Include related items and payments for detailed view
    items: List['PurchaseOrderItem'] = []
    payments: List['Payment'] = []



    class Config:
        from_attributes = True