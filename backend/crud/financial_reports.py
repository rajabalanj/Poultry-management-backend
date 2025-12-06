from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from models import sales_orders, purchase_orders, inventory_items, payments, sales_payments, composition_usage_history, operational_expenses, business_partners, purchase_order_items, sales_order_items
from schemas.financial_reports import ProfitAndLoss, BalanceSheet, Assets, CurrentAssets, Liabilities, CurrentLiabilities
from schemas.ledgers import GeneralLedger, GeneralLedgerEntry, PurchaseLedger, PurchaseLedgerEntry, SalesLedger, SalesLedgerEntry, InventoryLedger, InventoryLedgerEntry
from datetime import date
from decimal import Decimal
from crud import app_config as crud_app_config

def get_profit_and_loss(db: Session, start_date: date, end_date: date, tenant_id: int) -> ProfitAndLoss:
    # 1. Calculate Revenue
    total_revenue = db.query(func.sum(sales_orders.SalesOrder.total_amount)).filter(
        sales_orders.SalesOrder.tenant_id == tenant_id,
        sales_orders.SalesOrder.order_date >= start_date,
        sales_orders.SalesOrder.order_date <= end_date,
        sales_orders.SalesOrder.deleted_at.is_(None)
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
        for item in usage.items:
            inventory_item = db.query(inventory_items.InventoryItem).get(item.inventory_item_id)
            if inventory_item:
                usage_cost += Decimal(item.weight) * inventory_item.average_cost
        cogs += usage_cost * usage.times

    # 3. Calculate Gross Profit
    gross_profit = total_revenue - cogs

    # 4. Calculate Operating Expenses
    operating_expenses = db.query(func.sum(operational_expenses.OperationalExpense.amount)).filter(
        operational_expenses.OperationalExpense.tenant_id == tenant_id,
        operational_expenses.OperationalExpense.date >= start_date,
        operational_expenses.OperationalExpense.date <= end_date,
        operational_expenses.OperationalExpense.deleted_at.is_(None)
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
        sales_payments.SalesPayment.payment_date <= as_of_date,
        sales_payments.SalesPayment.deleted_at.is_(None)
    ).scalar() or Decimal(0)
    total_purchase_payments = db.query(func.sum(payments.Payment.amount_paid)).filter(
        payments.Payment.tenant_id == tenant_id,
        payments.Payment.payment_date <= as_of_date,
        payments.Payment.deleted_at.is_(None)
    ).scalar() or Decimal(0)
    cash = total_sales_payments - total_purchase_payments

    # Accounts Receivable
    total_sales = db.query(func.sum(sales_orders.SalesOrder.total_amount)).filter(
        sales_orders.SalesOrder.tenant_id == tenant_id,
        sales_orders.SalesOrder.order_date <= as_of_date,
        sales_orders.SalesOrder.deleted_at.is_(None)
    ).scalar() or Decimal(0)
    total_sales_paid = db.query(func.sum(sales_payments.SalesPayment.amount_paid)).join(sales_orders.SalesOrder).filter(
        sales_orders.SalesOrder.tenant_id == tenant_id,
        sales_orders.SalesOrder.order_date <= as_of_date,
        sales_orders.SalesOrder.deleted_at.is_(None),
        sales_payments.SalesPayment.deleted_at.is_(None)
    ).scalar() or Decimal(0)
    accounts_receivable = total_sales - total_sales_paid

    # Inventory
    inventory_value = db.query(func.sum(inventory_items.InventoryItem.current_stock * inventory_items.InventoryItem.average_cost)).filter(inventory_items.InventoryItem.tenant_id == tenant_id).scalar() or Decimal(0)

    current_assets = CurrentAssets(cash=cash, accounts_receivable=accounts_receivable, inventory=inventory_value)
    assets = Assets(current_assets=current_assets)

    # 2. Calculate Liabilities
    # Accounts Payable
    total_purchases = db.query(func.sum(purchase_orders.PurchaseOrder.total_amount)).filter(
        purchase_orders.PurchaseOrder.tenant_id == tenant_id, 
        purchase_orders.PurchaseOrder.order_date <= as_of_date,
        purchase_orders.PurchaseOrder.deleted_at.is_(None)
        ).scalar() or Decimal(0)
    total_purchases_paid = db.query(func.sum(payments.Payment.amount_paid)).join(purchase_orders.PurchaseOrder).filter(
        purchase_orders.PurchaseOrder.tenant_id == tenant_id, 
        purchase_orders.PurchaseOrder.order_date <= as_of_date,
        purchase_orders.PurchaseOrder.deleted_at.is_(None),
        payments.Payment.deleted_at.is_(None)
        ).scalar() or Decimal(0)
    accounts_payable = total_purchases - total_purchases_paid

    current_liabilities = CurrentLiabilities(accounts_payable=accounts_payable)
    liabilities = Liabilities(current_liabilities=current_liabilities)

    # 3. Calculate Equity
    total_assets = cash + accounts_receivable + inventory_value
    total_liabilities = accounts_payable
    equity = total_assets - total_liabilities

    return BalanceSheet(assets=assets, liabilities=liabilities, equity=equity)

def get_general_ledger(db: Session, start_date: date, end_date: date, tenant_id: str) -> GeneralLedger:
    financial_config = crud_app_config.get_financial_config(db, tenant_id)
    initial_opening_balance = financial_config['general_ledger_opening_balance']

    # Get all transactions before the start date to calculate the report opening balance

    prior_sales_payments = db.query(sales_payments.SalesPayment).filter(
        sales_payments.SalesPayment.tenant_id == tenant_id,
        sales_payments.SalesPayment.payment_date < start_date,
        sales_payments.SalesPayment.deleted_at.is_(None)
    ).all()

    prior_purchase_payments = db.query(payments.Payment).filter(
        payments.Payment.tenant_id == tenant_id,
        payments.Payment.payment_date < start_date,
        payments.Payment.deleted_at.is_(None)
    ).all()

    # Calculate the net effect of prior transactions
    prior_net_effect = 0.0
    for sp in prior_sales_payments:
        prior_net_effect += float(sp.amount_paid)  # Credits are positive

    for pp in prior_purchase_payments:
        prior_net_effect -= float(pp.amount_paid)  # Debits are negative

    # Calculate the report opening balance
    report_opening_balance = initial_opening_balance + prior_net_effect

    # Get transactions within the date range
    sales_payments_query = db.query(sales_payments.SalesPayment).join(sales_orders.SalesOrder).join(business_partners.BusinessPartner).filter(
        sales_payments.SalesPayment.tenant_id == tenant_id,
        sales_payments.SalesPayment.payment_date >= start_date,
        sales_payments.SalesPayment.payment_date <= end_date,
        sales_payments.SalesPayment.deleted_at.is_(None)
    ).all()

    purchase_payments_query = db.query(payments.Payment).join(purchase_orders.PurchaseOrder).join(business_partners.BusinessPartner).filter(
        payments.Payment.tenant_id == tenant_id,
        payments.Payment.payment_date >= start_date,
        payments.Payment.payment_date <= end_date,
        payments.Payment.deleted_at.is_(None)
    ).all()

    transactions = []
    for sp in sales_payments_query:
        transactions.append({
            "date": sp.payment_date,
            "transaction_type": "Sales Payment",
            "party": sp.sales_order.customer.name,
            "reference_document": f"SO-{sp.sales_order.so_number}",
            "transaction_id": sp.id,
            "reference_id": sp.sales_order.id,
            "details": f"Payment received for Sales Order SO-{sp.sales_order.so_number}",
            "debit": 0.0,
            "credit": float(sp.amount_paid)
        })

    for pp in purchase_payments_query:
        transactions.append({
            "date": pp.payment_date,
            "transaction_type": "Purchase Payment",
            "party": pp.purchase_order.vendor.name,
            "reference_document": f"PO-{pp.purchase_order.po_number}",
            "transaction_id": pp.id,
            "reference_id": pp.purchase_order.id,
            "details": f"Payment made for Purchase Order PO-{pp.purchase_order.po_number}",
            "debit": float(pp.amount_paid),
            "credit": 0.0
        })

    transactions.sort(key=lambda x: x['date'])

    balance = report_opening_balance
    entries = []
    for t in transactions:
        balance += t['credit'] - t['debit']
        entries.append(GeneralLedgerEntry(**t, balance=balance))

    return GeneralLedger(
        title="General Ledger (Cash Account)",
        opening_balance=report_opening_balance,
        entries=entries,
        closing_balance=balance
    )

def get_purchase_ledger(db: Session, vendor_id: int, tenant_id: str) -> PurchaseLedger:
    vendor = db.query(business_partners.BusinessPartner).filter(business_partners.BusinessPartner.id == vendor_id, business_partners.BusinessPartner.tenant_id == tenant_id).first()
    
    purchase_orders_query = db.query(purchase_orders.PurchaseOrder).filter(
        purchase_orders.PurchaseOrder.vendor_id == vendor_id,
        purchase_orders.PurchaseOrder.tenant_id == tenant_id,
        purchase_orders.PurchaseOrder.deleted_at.is_(None)
    ).all()

    entries = []
    for po in purchase_orders_query:
        amount_paid = sum(p.amount_paid for p in po.payments if p.deleted_at is None)
        balance_amount = po.total_amount - amount_paid
        entries.append(PurchaseLedgerEntry(
            date=po.order_date,
            vendor_name=vendor.name,
            invoice_number=f"PO-{po.po_number}",
            description=po.notes,
            amount=float(po.total_amount),
            amount_paid=float(amount_paid),
            balance_amount=float(balance_amount),
            payment_status=po.status.value
        ))

    return PurchaseLedger(
        title=f"Purchase Ledger for {vendor.name}",
        vendor_id=vendor_id,
        entries=entries
    )

def get_sales_ledger(db: Session, customer_id: int, tenant_id: str) -> SalesLedger:
    customer = db.query(business_partners.BusinessPartner).filter(business_partners.BusinessPartner.id == customer_id, business_partners.BusinessPartner.tenant_id == tenant_id).first()

    sales_orders_query = db.query(sales_orders.SalesOrder).filter(
        sales_orders.SalesOrder.customer_id == customer_id,
        sales_orders.SalesOrder.tenant_id == tenant_id,
        sales_orders.SalesOrder.deleted_at.is_(None)
    ).all()

    entries = []
    for so in sales_orders_query:
        amount_paid = sum(p.amount_paid for p in so.payments if p.deleted_at is None)
        balance_amount = so.total_amount - amount_paid
        entries.append(SalesLedgerEntry(
            date=so.order_date,
            customer_name=customer.name,
            invoice_number=f"SO-{so.so_number}",
            description=so.notes,
            amount=float(so.total_amount),
            amount_paid=float(amount_paid),
            balance_amount=float(balance_amount),
            payment_status=so.status.value
        ))

    return SalesLedger(
        title=f"Sales Ledger for {customer.name}",
        customer_id=customer_id,
        entries=entries
    )

def get_inventory_ledger(db: Session, item_id: int, start_date: date, end_date: date, tenant_id: str) -> InventoryLedger:
    item = db.query(inventory_items.InventoryItem).filter(inventory_items.InventoryItem.id == item_id, inventory_items.InventoryItem.tenant_id == tenant_id).first()

    # Calculate opening quantity
    purchases_before = db.query(func.sum(purchase_order_items.PurchaseOrderItem.quantity)).join(purchase_orders.PurchaseOrder).filter(
        purchase_order_items.PurchaseOrderItem.inventory_item_id == item_id,
        purchase_orders.PurchaseOrder.tenant_id == tenant_id,
        purchase_orders.PurchaseOrder.order_date < start_date,
        purchase_orders.PurchaseOrder.deleted_at.is_(None)
    ).scalar() or 0.0

    sales_before = db.query(func.sum(sales_order_items.SalesOrderItem.quantity)).join(sales_orders.SalesOrder).filter(
        sales_order_items.SalesOrderItem.inventory_item_id == item_id,
        sales_orders.SalesOrder.tenant_id == tenant_id,
        sales_orders.SalesOrder.order_date < start_date,
        sales_orders.SalesOrder.deleted_at.is_(None)
    ).scalar() or 0.0

    opening_quantity = float(purchases_before) - float(sales_before)

    # Get transactions within the date range
    purchase_items = db.query(purchase_order_items.PurchaseOrderItem).join(purchase_orders.PurchaseOrder).filter(
        purchase_order_items.PurchaseOrderItem.inventory_item_id == item_id,
        purchase_orders.PurchaseOrder.tenant_id == tenant_id,
        purchase_orders.PurchaseOrder.order_date >= start_date,
        purchase_orders.PurchaseOrder.order_date <= end_date,
        purchase_orders.PurchaseOrder.deleted_at.is_(None)
    ).all()

    sales_items = db.query(sales_order_items.SalesOrderItem).join(sales_orders.SalesOrder).filter(
        sales_order_items.SalesOrderItem.inventory_item_id == item_id,
        sales_orders.SalesOrder.tenant_id == tenant_id,
        sales_orders.SalesOrder.order_date >= start_date,
        sales_orders.SalesOrder.order_date <= end_date,
        sales_orders.SalesOrder.deleted_at.is_(None)
    ).all()

    transactions = []
    for pi in purchase_items:
        transactions.append({
            "date": pi.purchase_order.order_date,
            "type": "purchase",
            "reference": f"PO-{pi.purchase_order.po_number}",
            "quantity_received": float(pi.quantity),
            "unit_cost": float(pi.price_per_unit),
            "total_cost": float(pi.quantity * pi.price_per_unit),
            "quantity_sold": 0.0
        })

    for si in sales_items:
        transactions.append({
            "date": si.sales_order.order_date,
            "type": "sale",
            "reference": f"SO-{si.sales_order.so_number}",
            "quantity_received": 0.0,
            "unit_cost": 0.0,
            "total_cost": 0.0,
            "quantity_sold": float(si.quantity)
        })

    transactions.sort(key=lambda x: x['date'])

    quantity_on_hand = opening_quantity
    entries = []
    for t in transactions:
        if t['type'] == 'purchase':
            quantity_on_hand += t['quantity_received']
        else:
            quantity_on_hand -= t['quantity_sold']
        
        entries.append(InventoryLedgerEntry(
            date=t['date'],
            reference=t['reference'],
            quantity_received=t.get('quantity_received'),
            unit_cost=t.get('unit_cost'),
            total_cost=t.get('total_cost'),
            quantity_sold=t.get('quantity_sold'),
            quantity_on_hand=quantity_on_hand
        ))

    return InventoryLedger(
        title=f"Inventory Ledger for {item.name}",
        item_id=item_id,
        opening_quantity=opening_quantity,
        entries=entries,
        closing_quantity_on_hand=quantity_on_hand
    )
