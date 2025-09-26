from sqlalchemy.orm import Session
from sqlalchemy import func
from models import sales_orders, purchase_orders, inventory_items, payments, sales_payments, composition_usage_history
from schemas.financial_reports import ProfitAndLoss, BalanceSheet, Assets, CurrentAssets, Liabilities, CurrentLiabilities
from datetime import date
from decimal import Decimal

def get_profit_and_loss(db: Session, start_date: date, end_date: date, tenant_id: int) -> ProfitAndLoss:
    # 1. Calculate Revenue
    total_revenue = db.query(func.sum(sales_orders.SalesOrder.total_amount)).filter(
        sales_orders.SalesOrder.tenant_id == tenant_id,
        sales_orders.SalesOrder.order_date >= start_date,
        sales_orders.SalesOrder.order_date <= end_date
    ).scalar() or Decimal(0)

    # 2. Calculate COGS (Cost of Goods Sold)
    cogs = Decimal(0)
    composition_usages = db.query(composition_usage_history.CompositionUsageHistory).filter(
        composition_usage_history.CompositionUsageHistory.tenant_id == tenant_id,
        composition_usage_history.CompositionUsageHistory.used_at >= start_date,
        composition_usage_history.CompositionUsageHistory.used_at <= end_date
    ).all()

    # This loop performs N+1 queries. Consider optimizing if performance becomes an issue.
    for usage in composition_usages:
        usage_cost = Decimal(0)
        for item in usage.composition_items:
            inventory_item = db.query(inventory_items.InventoryItem).get(item['inventory_item_id'])
            if inventory_item:
                usage_cost += Decimal(item['weight']) * inventory_item.average_cost
        cogs += usage_cost * usage.times

    # 3. Calculate Gross Profit
    gross_profit = total_revenue - cogs

    # 4. Calculate Operating Expenses
    operating_expenses = db.query(func.sum(purchase_orders.PurchaseOrder.total_amount)).join(purchase_orders.PurchaseOrder.items).join(inventory_items.InventoryItem).filter(
        purchase_orders.PurchaseOrder.tenant_id == tenant_id,
        purchase_orders.PurchaseOrder.order_date >= start_date,
        purchase_orders.PurchaseOrder.order_date <= end_date,
        ~inventory_items.InventoryItem.category.in_(['Feed', 'Medicine'])
    ).scalar() or Decimal(0)

    # 5. Calculate Net Income
    net_income = gross_profit - operating_expenses

    return ProfitAndLoss(
        revenue=total_revenue,
        cogs=cogs,
        gross_profit=gross_profit,
        operating_expenses=operating_expenses,
        net_income=net_income
    )

def get_balance_sheet(db: Session, as_of_date: date, tenant_id: int) -> BalanceSheet:
    # 1. Calculate Assets
    # Cash
    total_sales_payments = db.query(func.sum(sales_payments.SalesPayment.amount_paid)).filter(
        sales_payments.SalesPayment.tenant_id == tenant_id,
        sales_payments.SalesPayment.payment_date <= as_of_date
    ).scalar() or Decimal(0)
    total_purchase_payments = db.query(func.sum(payments.Payment.amount_paid)).filter(
        payments.Payment.tenant_id == tenant_id,
        payments.Payment.payment_date <= as_of_date
    ).scalar() or Decimal(0)
    cash = total_sales_payments - total_purchase_payments

    # Accounts Receivable
    total_sales = db.query(func.sum(sales_orders.SalesOrder.total_amount)).filter(
        sales_orders.SalesOrder.tenant_id == tenant_id,
        sales_orders.SalesOrder.order_date <= as_of_date
    ).scalar() or Decimal(0)
    total_sales_paid = db.query(func.sum(sales_payments.SalesPayment.amount_paid)).join(sales_orders.SalesOrder).filter(
        sales_orders.SalesOrder.tenant_id == tenant_id,
        sales_orders.SalesOrder.order_date <= as_of_date
    ).scalar() or Decimal(0)
    accounts_receivable = total_sales - total_sales_paid

    # Inventory
    inventory_value = db.query(func.sum(inventory_items.InventoryItem.current_stock * inventory_items.InventoryItem.average_cost)).filter(inventory_items.InventoryItem.tenant_id == tenant_id).scalar() or Decimal(0)

    current_assets = CurrentAssets(cash=cash, accounts_receivable=accounts_receivable, inventory=inventory_value)
    assets = Assets(current_assets=current_assets)

    # 2. Calculate Liabilities
    # Accounts Payable
    total_purchases = db.query(func.sum(purchase_orders.PurchaseOrder.total_amount)).filter(purchase_orders.PurchaseOrder.tenant_id == tenant_id, purchase_orders.PurchaseOrder.order_date <= as_of_date).scalar() or Decimal(0)
    total_purchases_paid = db.query(func.sum(payments.Payment.amount_paid)).join(purchase_orders.PurchaseOrder).filter(purchase_orders.PurchaseOrder.tenant_id == tenant_id, purchase_orders.PurchaseOrder.order_date <= as_of_date).scalar() or Decimal(0)
    accounts_payable = total_purchases - total_purchases_paid

    current_liabilities = CurrentLiabilities(accounts_payable=accounts_payable)
    liabilities = Liabilities(current_liabilities=current_liabilities)

    # 3. Calculate Equity
    total_assets = cash + accounts_receivable + inventory_value
    total_liabilities = accounts_payable
    equity = total_assets - total_liabilities

    return BalanceSheet(assets=assets, liabilities=liabilities, equity=equity)
