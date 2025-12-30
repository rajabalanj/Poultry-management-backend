from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from models.sales_orders import SalesOrder, SalesOrderStatus
from models.sales_order_items import SalesOrderItem
from models.business_partners import BusinessPartner
from models.inventory_items import InventoryItem
from schemas.sales_order_reports import SalesOrderReport, SalesOrderItemReport
from datetime import date

def get_sales_order_report(
    db: Session, 
    tenant_id: str,
    skip: int = 0,
    limit: int = 100,
    customer_id: Optional[int] = None,
    status: Optional[SalesOrderStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> List[SalesOrderReport]:
    """
    Retrieves a detailed sales order report for a given tenant.
    """
    query = (
        db.query(SalesOrder)
        .options(
            joinedload(SalesOrder.customer),
            joinedload(SalesOrder.items).joinedload(SalesOrderItem.inventory_item),
        )
        .filter(SalesOrder.tenant_id == tenant_id)
    )

    if customer_id:
        query = query.filter(SalesOrder.customer_id == customer_id)
    if status:
        query = query.filter(SalesOrder.status == status)
    if start_date:
        query = query.filter(SalesOrder.order_date >= start_date)
    if end_date:
        query = query.filter(SalesOrder.order_date <= end_date)

    sales_orders = (
        query.order_by(SalesOrder.order_date.desc(), SalesOrder.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    report_data = []
    for so in sales_orders:
        items_data = [
            SalesOrderItemReport(
                inventory_item_name=item.inventory_item.name,
                quantity=item.quantity,
                price_per_unit=item.price_per_unit,
                line_total=item.line_total,
                variant_name=item.variant_name,
            )
            for item in so.items
        ]

        report_data.append(
            SalesOrderReport(
                so_number=so.so_number,
                bill_no=so.bill_no,
                customer_name=so.customer.name,
                order_date=so.order_date,
                total_amount=so.total_amount,
                total_amount_paid=so.total_amount_paid,
                status=so.status,
                items=items_data,
            )
        )

    return report_data
