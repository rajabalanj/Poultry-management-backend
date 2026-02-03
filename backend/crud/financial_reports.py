from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from models import sales_orders, purchase_orders, inventory_items, payments, sales_payments, composition_usage_history, operational_expenses, business_partners, purchase_order_items, sales_order_items, composition_usage_item
from models.egg_room_reports import EggRoomReport
from schemas.financial_reports import ProfitAndLoss, BalanceSheet, Assets, CurrentAssets, Liabilities, CurrentLiabilities
from schemas.ledgers import GeneralLedger, GeneralLedgerEntry, PurchaseLedger, PurchaseLedgerEntry, SalesLedger, SalesLedgerEntry, InventoryLedger, InventoryLedgerEntry
from datetime import date
from decimal import Decimal
from crud import app_config as crud_app_config
from crud.egg_room_reports import get_reports_by_date_range


def get_profit_and_loss(db: Session, start_date: date, end_date: date, tenant_id: int) -> ProfitAndLoss:
    # 1. Calculate Revenue
    total_revenue = db.query(func.sum(sales_orders.SalesOrder.total_amount)).filter(
        sales_orders.SalesOrder.tenant_id == tenant_id,
        sales_orders.SalesOrder.order_date >= start_date,
        sales_orders.SalesOrder.order_date <= end_date,
        sales_orders.SalesOrder.deleted_at.is_(None)
    ).scalar() or Decimal(0)

    # 2. Calculate COGS (Cost of Goods Sold)
    composition_usages = db.query(composition_usage_history.CompositionUsageHistory).options(
        joinedload(composition_usage_history.CompositionUsageHistory.items)
        .joinedload(composition_usage_item.CompositionUsageItem.inventory_item)
    ).filter(
        composition_usage_history.CompositionUsageHistory.tenant_id == tenant_id,
        composition_usage_history.CompositionUsageHistory.used_at >= start_date,
        composition_usage_history.CompositionUsageHistory.used_at <= end_date
    ).all()

    cogs = Decimal(0)
    for usage in composition_usages:
        usage_cost = Decimal(0)
        for item in usage.items:
            if item.inventory_item:
                usage_cost += Decimal(item.weight) * item.inventory_item.average_cost
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
    total_sales_paid = db.query(func.sum(sales_payments.SalesPayment.amount_paid)).join(sales_orders.SalesOrder).filter(
        sales_orders.SalesOrder.tenant_id == tenant_id,
        sales_payments.SalesPayment.payment_date <= as_of_date,
        sales_orders.SalesOrder.deleted_at.is_(None),
        sales_payments.SalesPayment.deleted_at.is_(None)
    ).scalar() or Decimal(0)
    total_purchases_paid = db.query(func.sum(payments.Payment.amount_paid)).join(purchase_orders.PurchaseOrder).filter(
        purchase_orders.PurchaseOrder.tenant_id == tenant_id, 
        payments.Payment.payment_date <= as_of_date,
        purchase_orders.PurchaseOrder.deleted_at.is_(None),
        payments.Payment.deleted_at.is_(None)
    ).scalar() or Decimal(0)
    total_operational_expenses = db.query(func.sum(operational_expenses.OperationalExpense.amount)).filter(
    operational_expenses.OperationalExpense.tenant_id == tenant_id,
    operational_expenses.OperationalExpense.date <= as_of_date,
    operational_expenses.OperationalExpense.deleted_at.is_(None)
    ).scalar() or Decimal(0)
    financial_config = crud_app_config.get_financial_config(db, tenant_id)
    opening_balance = Decimal(str(financial_config.get('general_ledger_opening_balance', 0.0)))
    cash = opening_balance + total_sales_paid - total_purchases_paid - total_operational_expenses

    # Accounts Receivable
    total_sales = db.query(func.sum(sales_orders.SalesOrder.total_amount)).filter(
        sales_orders.SalesOrder.tenant_id == tenant_id,
        sales_orders.SalesOrder.order_date <= as_of_date,
        sales_orders.SalesOrder.deleted_at.is_(None)
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
    accounts_payable = total_purchases - total_purchases_paid

    current_liabilities = CurrentLiabilities(accounts_payable=accounts_payable)
    liabilities = Liabilities(current_liabilities=current_liabilities)

    # 3. Calculate Equity
    total_assets = cash + accounts_receivable + inventory_value
    total_liabilities = accounts_payable
    equity = total_assets - total_liabilities

    return BalanceSheet(assets=assets, liabilities=liabilities, equity=equity)

def get_general_ledger(db: Session, start_date: date, end_date: date, tenant_id: str, transaction_type: str = None) -> GeneralLedger:
    financial_config = crud_app_config.get_financial_config(db, tenant_id)
    initial_opening_balance = Decimal(financial_config.get('general_ledger_opening_balance', '0.0'))

    # Get all transactions before the start date to calculate the report opening balance
    prior_sales_payments = []
    if transaction_type is None or transaction_type == 'sales':
        prior_sales_payments = db.query(sales_payments.SalesPayment).filter(
            sales_payments.SalesPayment.tenant_id == tenant_id,
            sales_payments.SalesPayment.payment_date < start_date,
            sales_payments.SalesPayment.deleted_at.is_(None)
        ).all()

    prior_purchase_payments = []
    if transaction_type is None or transaction_type == 'purchase':
        prior_purchase_payments = db.query(payments.Payment).filter(
            payments.Payment.tenant_id == tenant_id,
            payments.Payment.payment_date < start_date,
            payments.Payment.deleted_at.is_(None)
        ).all()

    # Calculate the net effect of prior transactions
    prior_net_effect = Decimal('0.0')
    for sp in prior_sales_payments:
        prior_net_effect += sp.amount_paid  # Credits are positive

    for pp in prior_purchase_payments:
        prior_net_effect -= pp.amount_paid  # Debits are negative

    # Calculate the report opening balance
    report_opening_balance = initial_opening_balance + prior_net_effect

    # Get transactions within the date range
    sales_payments_query = []
    if transaction_type is None or transaction_type == 'sales':
        sales_payments_query = db.query(sales_payments.SalesPayment).options(joinedload(sales_payments.SalesPayment.sales_order).joinedload(sales_orders.SalesOrder.customer)).filter(
            sales_payments.SalesPayment.tenant_id == tenant_id,
            sales_payments.SalesPayment.payment_date >= start_date,
            sales_payments.SalesPayment.payment_date <= end_date,
            sales_payments.SalesPayment.deleted_at.is_(None)
        ).all()

    purchase_payments_query = []
    if transaction_type is None or transaction_type == 'purchase':
        purchase_payments_query = db.query(payments.Payment).options(joinedload(payments.Payment.purchase_order).joinedload(purchase_orders.PurchaseOrder.vendor)).filter(
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
            "details": f"Payment for SO-{sp.sales_order.so_number}" + (f" ({sp.notes})" if sp.notes else ""),
            "debit": Decimal('0.0'),
            "credit": sp.amount_paid
        })

    for pp in purchase_payments_query:
        transactions.append({
            "date": pp.payment_date,
            "transaction_type": "Purchase Payment",
            "party": pp.purchase_order.vendor.name,
            "reference_document": f"PO-{pp.purchase_order.po_number}",
            "transaction_id": pp.id,
            "reference_id": pp.purchase_order.id,
            "details": f"Payment for PO-{pp.purchase_order.po_number}" + (f" ({pp.notes})" if pp.notes else ""),
            "debit": pp.amount_paid,
            "credit": Decimal('0.0')
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
    
    purchase_orders_query = db.query(purchase_orders.PurchaseOrder).options(joinedload(purchase_orders.PurchaseOrder.payments)).filter(
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
            po_id=po.id,
            invoice_number=f"PO-{po.po_number}",
            description=po.notes,
            amount=po.total_amount,
            amount_paid=amount_paid,
            balance_amount=balance_amount,
            payment_status=po.status.value
        ))

    return PurchaseLedger(
        title=f"Purchase Ledger for {vendor.name}",
        vendor_id=vendor_id,
        entries=entries
    )

def get_sales_ledger(db: Session, customer_id: int, tenant_id: str) -> SalesLedger:
    customer = db.query(business_partners.BusinessPartner).filter(business_partners.BusinessPartner.id == customer_id, business_partners.BusinessPartner.tenant_id == tenant_id).first()

    sales_orders_query = db.query(sales_orders.SalesOrder).options(joinedload(sales_orders.SalesOrder.payments)).filter(
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
            so_id=so.id,
            invoice_number=f"SO-{so.so_number}",
            description=so.notes,
            amount=so.total_amount,
            amount_paid=amount_paid,
            balance_amount=balance_amount,
            payment_status=so.status.value
        ))

    return SalesLedger(
        title=f"Sales Ledger for {customer.name}",
        customer_id=customer_id,
        entries=entries
    )

def get_inventory_ledger(db: Session, item_id: int, start_date: date, end_date: date, tenant_id: str) -> InventoryLedger:
    item = db.query(inventory_items.InventoryItem).filter(
        inventory_items.InventoryItem.id == item_id, 
        inventory_items.InventoryItem.tenant_id == tenant_id
    ).first()

    if not item:
        return None  # Or raise an exception

    # Special handling for "egg" items
    if 'egg' in item.name.lower():
        reports = get_reports_by_date_range(db, start_date.isoformat(), end_date.isoformat(), tenant_id)
        
        opening_quantity = Decimal('0.0')
        closing_quantity = Decimal('0.0')
        entries = []
        
        if reports:
            start_report = reports[0]
            end_report = reports[-1]

            if "table" in item.name.lower():
                opening_quantity = start_report.table_opening or Decimal('0.0')
                closing_quantity = end_report.table_closing or Decimal('0.0')
            elif "jumbo" in item.name.lower():
                opening_quantity = start_report.jumbo_opening or Decimal('0.0')
                closing_quantity = end_report.jumbo_closing or Decimal('0.0')
            elif "grade c" in item.name.lower():
                opening_quantity = start_report.grade_c_opening or Decimal('0.0')
                closing_quantity = end_report.grade_c_closing or Decimal('0.0')

            for report in reports:
                quantity_received = Decimal('0.0')
                quantity_sold = Decimal('0.0')
                quantity_on_hand = Decimal('0.0')
                reference = "Daily Egg Room Report"

                if "table" in item.name.lower():
                    quantity_received = (report.table_received or 0) + (report.jumbo_out or 0)
                    quantity_sold = (report.table_transfer or 0) + (report.table_out or 0) + (report.table_damage or 0)
                    quantity_on_hand = report.table_closing or 0
                elif "jumbo" in item.name.lower():
                    quantity_received = (report.jumbo_received or 0) + (report.table_out or 0)
                    quantity_sold = (report.jumbo_transfer or 0) + (report.jumbo_out or 0) + (report.jumbo_waste or 0)
                    quantity_on_hand = report.jumbo_closing or 0
                elif "grade c" in item.name.lower():
                    quantity_received = (report.grade_c_shed_received or 0) + (report.table_damage or 0)
                    quantity_sold = (report.grade_c_transfer or 0) + (report.grade_c_labour or 0) + (report.grade_c_waste or 0)
                    quantity_on_hand = report.grade_c_closing or 0
                
                # Only create an entry if there was some activity
                if quantity_received > 0 or quantity_sold > 0:
                    entries.append(InventoryLedgerEntry(
                        date=report.report_date,
                        reference=reference,
                        quantity_received=quantity_received,
                        unit_cost=item.average_cost,
                        total_cost=quantity_received * item.average_cost,
                        quantity_sold=quantity_sold,
                        quantity_on_hand=quantity_on_hand
                    ))

        return InventoryLedger(
            title=f"Inventory Ledger for {item.name}",
            item_id=item_id,
            opening_quantity=opening_quantity,
            entries=entries,
            closing_quantity_on_hand=closing_quantity
        )

    # Calculate opening quantity for non-egg items
    purchases_before = db.query(func.sum(purchase_order_items.PurchaseOrderItem.quantity)).join(purchase_orders.PurchaseOrder).filter(
        purchase_order_items.PurchaseOrderItem.inventory_item_id == item_id,
        purchase_orders.PurchaseOrder.tenant_id == tenant_id,
        purchase_orders.PurchaseOrder.order_date < start_date,
        purchase_orders.PurchaseOrder.deleted_at.is_(None)
    ).scalar() or Decimal('0.0')

    sales_before = db.query(func.sum(sales_order_items.SalesOrderItem.quantity)).join(sales_orders.SalesOrder).filter(
        sales_order_items.SalesOrderItem.inventory_item_id == item_id,
        sales_orders.SalesOrder.tenant_id == tenant_id,
        sales_orders.SalesOrder.order_date < start_date,
        sales_orders.SalesOrder.deleted_at.is_(None)
    ).scalar() or Decimal('0.0')

    opening_quantity = purchases_before - sales_before

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
            "quantity_received": pi.quantity,
            "unit_cost": pi.price_per_unit,
            "total_cost": pi.quantity * pi.price_per_unit,
            "quantity_sold": Decimal('0.0')
        })

    for si in sales_items:
        transactions.append({
            "date": si.sales_order.order_date,
            "type": "sale",
            "reference": f"SO-{si.sales_order.so_number}",
            "quantity_received": Decimal('0.0'),
            "unit_cost": Decimal('0.0'),
            "total_cost": Decimal('0.0'),
            "quantity_sold": si.quantity
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

