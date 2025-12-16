from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from models.sales_orders import SalesOrderStatus
from schemas.sales_order_items import SalesOrderItemCreateRequest
from schemas.sales_payments import SalesPayment as SalesPaymentSchema


class SalesOrderItem(BaseModel):
    id: int
    inventory_item_id: int
    quantity: Decimal
    price_per_unit: Decimal
    line_total: Decimal
    tenant_id: Optional[str] = None

    class Config:
        from_attributes = True

class SalesOrderBase(BaseModel):
    customer_id: int  # Now references business_partners table
    order_date: date
    status: Optional[SalesOrderStatus] = SalesOrderStatus.DRAFT
    notes: Optional[str] = None
    payment_receipt: Optional[str] = None
    bill_no: Optional[str] = None

class SalesOrderCreate(SalesOrderBase):
    items: List[SalesOrderItemCreateRequest]

class SalesOrderUpdate(BaseModel):
    customer_id: Optional[int] = None
    order_date: Optional[date] = None
    status: Optional[SalesOrderStatus] = None
    notes: Optional[str] = None
    payment_receipt: Optional[str] = None
    bill_no: Optional[str] = None

class SalesOrder(SalesOrderBase):
    id: int
    so_number: Optional[int] = None
    tenant_id: Optional[str] = None
    total_amount: Decimal
    total_amount_paid: Decimal
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    items: List['SalesOrderItem'] = []
    payments: List[SalesPaymentSchema] = []
    bill_no: Optional[str] = None

    class Config:
        from_attributes = True