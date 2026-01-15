from sqlalchemy.orm import Session
from datetime import date
from decimal import Decimal
from sqlalchemy import func

from models import (
    EggRoomReport,
    SalesOrderItem,
    CompositionUsageHistory,
    OperationalExpense,
    SalesOrder,
    SalesPayment,
    PurchaseOrder,
    Payment,
)
from schemas.financial_reports import FinancialSummary


def get_financial_summary(db: Session, start_date: date, end_date: date, tenant_id: str) -> FinancialSummary:
    """
    Calculates the financial summary for a given period for a specific tenant.
    """
    # Eggs Produced
    eggs_produced_query = db.query(
        func.sum(EggRoomReport.table_received).label("total_table"),
        func.sum(EggRoomReport.jumbo_received).label("total_jumbo"),
        func.sum(EggRoomReport.grade_c_shed_received).label("total_grade_c"),
    ).filter(
        EggRoomReport.report_date.between(start_date, end_date),
        EggRoomReport.tenant_id == tenant_id
    )
    
    eggs_produced_result = eggs_produced_query.one()
    eggs_produced = (eggs_produced_result.total_table or 0) + \
                    (eggs_produced_result.total_jumbo or 0) + \
                    (eggs_produced_result.total_grade_c or 0)

    # Eggs Sold
    eggs_sold_query = db.query(
        func.sum(EggRoomReport.table_transfer).label("total_table"),
        func.sum(EggRoomReport.jumbo_transfer).label("total_jumbo"),
        func.sum(EggRoomReport.grade_c_transfer).label("total_grade_c"),
    ).filter(
        EggRoomReport.report_date.between(start_date, end_date),
        EggRoomReport.tenant_id == tenant_id
    )
    
    eggs_sold_result = eggs_sold_query.one()
    eggs_sold = (eggs_sold_result.total_table or 0) + \
                (eggs_sold_result.total_jumbo or 0) + \
                (eggs_sold_result.total_grade_c or 0)

    # Cost per Egg
    cogs = Decimal(0)
    composition_usages = db.query(CompositionUsageHistory).filter(
        CompositionUsageHistory.used_at.between(start_date, end_date),
        CompositionUsageHistory.tenant_id == tenant_id
    ).all()

    for usage in composition_usages:
        usage_cost = Decimal(0)
        for item in usage.items:
            usage_cost += Decimal(item.weight) * item.inventory_item.average_cost
        cogs += usage_cost * usage.times

    operating_expenses = db.query(func.sum(OperationalExpense.amount)).filter(
        OperationalExpense.date.between(start_date, end_date),
        OperationalExpense.tenant_id == tenant_id
    ).scalar() or Decimal(0)

    total_cost = cogs + operating_expenses
    cost_per_egg = total_cost / eggs_produced if eggs_produced > 0 else Decimal(0)

    # Selling Price per Egg
    total_egg_revenue = db.query(func.sum(SalesOrderItem.line_total)).join(SalesOrder).filter(
        SalesOrder.order_date.between(start_date, end_date),
        SalesOrder.tenant_id == tenant_id
    ).scalar() or Decimal(0)

    selling_price_per_egg = total_egg_revenue / eggs_sold if eggs_sold > 0 else Decimal(0)

    # Net Margin per Egg
    net_margin_per_egg = selling_price_per_egg - cost_per_egg

    # Cash Balance, Receivables, and Payables (as of end_date)
    total_sales_payments = db.query(func.sum(SalesPayment.amount_paid)).filter(
        SalesPayment.payment_date <= end_date,
        SalesPayment.tenant_id == tenant_id
    ).scalar() or Decimal(0)
    
    total_purchase_payments = db.query(func.sum(Payment.amount_paid)).filter(
        Payment.payment_date <= end_date,
        Payment.tenant_id == tenant_id
    ).scalar() or Decimal(0)
    
    cash_balance = total_sales_payments - total_purchase_payments

    total_sales = db.query(func.sum(SalesOrder.total_amount)).filter(
        SalesOrder.order_date <= end_date,
        SalesOrder.tenant_id == tenant_id
    ).scalar() or Decimal(0)
    
    receivables = total_sales - total_sales_payments

    total_purchases = db.query(func.sum(PurchaseOrder.total_amount)).filter(
        PurchaseOrder.order_date <= end_date,
        PurchaseOrder.tenant_id == tenant_id
    ).scalar() or Decimal(0)
    
    payables = total_purchases - total_purchase_payments

    return FinancialSummary(
        eggs_produced=eggs_produced,
        eggs_sold=eggs_sold,
        cost_per_egg=cost_per_egg,
        selling_price_per_egg=selling_price_per_egg,
        net_margin_per_egg=net_margin_per_egg,
        cash_balance=cash_balance,
        receivables=receivables,
        payables=payables,
    )
