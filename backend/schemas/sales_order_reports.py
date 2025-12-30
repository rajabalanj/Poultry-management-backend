from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from decimal import Decimal
from models.sales_orders import SalesOrderStatus

class SalesOrderItemReport(BaseModel):
    inventory_item_name: str
    quantity: Decimal
    price_per_unit: Decimal
    line_total: Decimal
    variant_name: Optional[str] = None

    class Config:
        from_attributes = True


class SalesOrderReport(BaseModel):
    so_number: Optional[int]
    bill_no: Optional[str]
    customer_name: str
    order_date: date
    total_amount: Decimal
    total_amount_paid: Decimal
    status: SalesOrderStatus
    items: List[SalesOrderItemReport]

    class Config:
        from_attributes = True
