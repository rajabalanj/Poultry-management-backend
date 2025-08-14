from pydantic import BaseModel
from typing import Optional
from decimal import Decimal

class SalesOrderItemBase(BaseModel):
    inventory_item_id: int
    quantity: Decimal
    price_per_unit: Decimal

class SalesOrderItemCreateRequest(SalesOrderItemBase):
    pass

class SalesOrderItemCreate(SalesOrderItemBase):
    sales_order_id: int
    line_total: Decimal

class SalesOrderItemUpdate(BaseModel):
    quantity: Optional[Decimal] = None
    price_per_unit: Optional[Decimal] = None

class SalesOrderItem(SalesOrderItemBase):
    id: int
    sales_order_id: int
    line_total: Decimal

    class Config:
        from_attributes = True