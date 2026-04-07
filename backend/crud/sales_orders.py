from sqlalchemy.orm import Session, selectinload
from typing import List, Optional
from datetime import date
from models.sales_orders import SalesOrder as SalesOrderModel, SalesOrderStatus
from models.sales_order_items import SalesOrderItem as SalesOrderItemModel
from models.business_partners import BusinessPartner as BusinessPartnerModel
from models.sales_payments import SalesPayment as SalesPaymentModel

def get_sales_orders_for_customer_bill(
    db: Session,
    tenant_id: str,
    customer_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    status: Optional[str] = None
) -> List[SalesOrderModel]:
    """
    Retrieves sales orders for a specific customer, optionally filtered by date range and status,
    eagerly loading related items and payments for bill generation.
    """
    query = db.query(SalesOrderModel).options(
        selectinload(SalesOrderModel.items).selectinload(SalesOrderItemModel.inventory_item),
        selectinload(SalesOrderModel.payments)
    ).filter(
        SalesOrderModel.tenant_id == tenant_id,
        SalesOrderModel.customer_id == customer_id
    )

    if start_date:
        query = query.filter(SalesOrderModel.order_date >= start_date)
    if end_date:
        query = query.filter(SalesOrderModel.order_date <= end_date)
    if status:
        if status == "paid":
            query = query.filter(SalesOrderModel.status == SalesOrderStatus.PAID)
        elif status == "unpaid":
            query = query.filter(SalesOrderModel.status != SalesOrderStatus.PAID)

    sales_orders = query.order_by(SalesOrderModel.order_date.asc()).all()

    # Filter out soft-deleted payments
    for so in sales_orders:
        so.payments = [p for p in so.payments if p.deleted_at is None]

    return sales_orders