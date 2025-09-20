from pydantic import BaseModel
from typing import Optional
from decimal import Decimal

class PurchaseOrderItemBase(BaseModel):
    inventory_item_id: int
    quantity: Decimal
    price_per_unit: Decimal

class PurchaseOrderItemCreateRequest(PurchaseOrderItemBase):
    # Used when creating/adding items to a PO in a request body
    pass

class PurchaseOrderItemCreate(PurchaseOrderItemBase):
    # Used internally after initial calculation, includes line_total
    purchase_order_id: int
    line_total: Decimal
    tenant_id: Optional[str] = None

class PurchaseOrderItemUpdate(BaseModel):
    quantity: Optional[Decimal] = None
    price_per_unit: Optional[Decimal] = None

class PurchaseOrderItem(PurchaseOrderItemBase):
    id: int
    purchase_order_id: int
    line_total: Decimal
    tenant_id: Optional[str] = None

    class Config:
        from_attributes = True  