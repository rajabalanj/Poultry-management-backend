from pydantic import BaseModel
from typing import Optional
from decimal import Decimal

class SalesOrderItemBase(BaseModel):
    inventory_item_id: int
    quantity: Decimal
    price_per_unit: Decimal
    variant_id: Optional[int] = None
    variant_name: Optional[str] = None

class SalesOrderItemCreateRequest(SalesOrderItemBase):
    pass

class SalesOrderItemCreate(SalesOrderItemBase):
    sales_order_id: int
    line_total: Decimal
    tenant_id: Optional[str] = None

class SalesOrderItemUpdate(BaseModel):
    inventory_item_id: Optional[int] = None
    quantity: Optional[Decimal] = None
    price_per_unit: Optional[Decimal] = None
    variant_id: Optional[int] = None
    variant_name: Optional[str] = None

class SalesOrderItem(SalesOrderItemBase):
    id: int
    sales_order_id: int
    line_total: Decimal
    tenant_id: Optional[str] = None

    class Config:
        from_attributes = True