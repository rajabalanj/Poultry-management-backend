from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, case
from models.journal_entry import JournalEntry
from models.journal_item import JournalItem
from models.chart_of_accounts import ChartOfAccounts
from models.financial_settings import FinancialSettings
from models import business_partners, purchase_orders, sales_orders
from schemas.financial_reports import ProfitAndLoss, BalanceSheet, Assets, CurrentAssets, Liabilities, CurrentLiabilities
from schemas.ledgers import GeneralLedger, GeneralLedgerEntry, PurchaseLedger, PurchaseLedgerEntry, SalesLedger, SalesLedgerEntry, InventoryLedger, InventoryLedgerEntry
from datetime import date
from datetime import datetime
from decimal import Decimal
from crud import app_config as crud_app_config
from crud.egg_room_reports import get_reports_by_date_range
from models import purchase_order_items, sales_order_items, inventory_items


def get_profit_and_loss(db: Session, start_date: date, end_date: date, tenant_id: str) -> ProfitAndLoss:
    # Helper to calculate net balance (Credit - Debit) for a specific account type
    # Positive result means Credit > Debit (good for Revenue)
    # Negative result means Debit > Credit (good for Expense)
    def get_net_credit_balance(account_type):
        return db.query(func.sum(JournalItem.credit - JournalItem.debit)).join(ChartOfAccounts).join(JournalEntry).filter(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.date >= start_date,
            JournalEntry.date <= end_date,
            ChartOfAccounts.account_type == account_type
        ).scalar() or Decimal(0)

    # 1. Revenue (Credit Normal)
    total_revenue = get_net_credit_balance('Revenue')

    # 2. Expenses (Debit Normal, so get_net_credit_balance returns negative)
    # We negate it to get a positive expense number
    total_expenses_net = -get_net_credit_balance('Expense')

    # 3. Identify COGS specifically
    settings = db.query(FinancialSettings).filter(FinancialSettings.tenant_id == tenant_id).first()
    cogs = Decimal(0)
    
    if settings and settings.default_cogs_account_id:
        # Calculate COGS specifically (Debit - Credit)
        cogs = db.query(func.sum(JournalItem.debit - JournalItem.credit)).join(JournalEntry).filter(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.date >= start_date,
            JournalEntry.date <= end_date,
            JournalItem.account_id == settings.default_cogs_account_id
        ).scalar() or Decimal(0)

    # 4. Operating Expenses = Total Expenses - COGS
    operating_expenses = total_expenses_net - cogs

    # 5. Gross Profit & Net Income
    gross_profit = total_revenue - cogs
    net_income = total_revenue - total_expenses_net

    # 6. Detailed Expense Breakdown
    # Query all expense accounts excluding COGS
    expense_breakdown_query = db.query(
        ChartOfAccounts.account_code,
        ChartOfAccounts.account_name,
        func.sum(JournalItem.debit - JournalItem.credit).label('amount')
    ).join(JournalItem).join(JournalEntry).filter(
        JournalEntry.tenant_id == tenant_id,
        JournalEntry.date >= start_date,
        JournalEntry.date <= end_date,
        ChartOfAccounts.account_type == 'Expense'
    )
    
    if settings and settings.default_cogs_account_id:
        expense_breakdown_query = expense_breakdown_query.filter(ChartOfAccounts.id != settings.default_cogs_account_id)
        
    expense_breakdown = expense_breakdown_query.group_by(ChartOfAccounts.id, ChartOfAccounts.account_code, ChartOfAccounts.account_name).all()
    
    expenses_by_account = []
    for code, name, amount in expense_breakdown:
        expenses_by_account.append({
            "account_code": code,
            "account_name": name,
            "amount": Decimal(str(amount))
        })

    return ProfitAndLoss(
        revenue=total_revenue,
        cogs=cogs,
        gross_profit=gross_profit,
        operating_expenses=operating_expenses,
        operating_expenses_by_account=expenses_by_account,
        net_income=net_income
    )

def get_balance_sheet(db: Session, as_of_date: date, tenant_id: str) -> BalanceSheet:
    # Helper for cumulative balance (Debit - Credit for Assets, Credit - Debit for others)
    def get_cumulative_balance(account_type, normal_balance='debit'):
        balance = db.query(func.sum(JournalItem.debit - JournalItem.credit)).join(ChartOfAccounts).join(JournalEntry).filter(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.date <= as_of_date,
            ChartOfAccounts.account_type == account_type
        ).scalar() or Decimal(0)
        return balance if normal_balance == 'debit' else -balance

    # 1. Assets
    total_assets = get_cumulative_balance('Asset', 'debit')
    
    # Breakdown Assets
    settings = db.query(FinancialSettings).filter(FinancialSettings.tenant_id == tenant_id).first()
    cash = Decimal(0)
    inventory = Decimal(0)
    
    if settings:
        if settings.default_cash_account_id:
            cash = db.query(func.sum(JournalItem.debit - JournalItem.credit)).join(JournalEntry).filter(
                JournalEntry.tenant_id == tenant_id,
                JournalEntry.date <= as_of_date,
                JournalItem.account_id == settings.default_cash_account_id
            ).scalar() or Decimal(0)
        
        if settings.default_inventory_account_id:
            inventory = db.query(func.sum(JournalItem.debit - JournalItem.credit)).join(JournalEntry).filter(
                JournalEntry.tenant_id == tenant_id,
                JournalEntry.date <= as_of_date,
                JournalItem.account_id == settings.default_inventory_account_id
            ).scalar() or Decimal(0)

    accounts_receivable = Decimal(0)
    if settings and settings.default_accounts_receivable_account_id:
        accounts_receivable = db.query(func.sum(JournalItem.debit - JournalItem.credit)).join(JournalEntry).filter(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.date <= as_of_date,
            JournalItem.account_id == settings.default_accounts_receivable_account_id
        ).scalar() or Decimal(0)

    current_assets = CurrentAssets(cash=cash, accounts_receivable=accounts_receivable, inventory=inventory)
    assets = Assets(current_assets=current_assets)

    # 2. Liabilities
    total_liabilities = get_cumulative_balance('Liability', 'credit')
    accounts_payable = Decimal(0)

    if settings and settings.default_accounts_payable_account_id:
        # For liabilities, the normal balance is credit. So we do Credit - Debit.
        accounts_payable = db.query(func.sum(JournalItem.credit - JournalItem.debit)).join(JournalEntry).filter(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.date <= as_of_date,
            JournalItem.account_id == settings.default_accounts_payable_account_id
        ).scalar() or Decimal(0)

    current_liabilities = CurrentLiabilities(accounts_payable=accounts_payable)
    liabilities = Liabilities(current_liabilities=current_liabilities)

    # 3. Equity
    # Equity = Equity Accounts + Retained Earnings (Net Income up to date)
    equity_accounts_total = get_cumulative_balance('Equity', 'credit')
    
    # Calculate Net Income (Revenue - Expenses) for Retained Earnings
    revenue_cum = get_cumulative_balance('Revenue', 'credit')
    expense_cum = get_cumulative_balance('Expense', 'debit') # Expense is debit normal
    net_income_cum = revenue_cum - expense_cum
    
    total_equity = equity_accounts_total + net_income_cum

    return BalanceSheet(assets=assets, liabilities=liabilities, equity=total_equity)

def get_general_ledger(db: Session, start_date: date, end_date: date, tenant_id: str, transaction_type: str = None, account_code: str = None) -> GeneralLedger:
    # 1. Calculate Opening Balance (Sum of all transactions before start_date)
    opening_balance_query = db.query(func.sum(JournalItem.debit - JournalItem.credit)).join(JournalEntry).join(ChartOfAccounts).filter(
        JournalEntry.tenant_id == tenant_id,
        JournalEntry.date < start_date
    )
    
    if account_code:
        opening_balance_query = opening_balance_query.filter(ChartOfAccounts.account_code == account_code)
    
    # Note: This opening balance logic assumes a Debit-normal view. 
    # For Credit-normal accounts (Liability/Equity/Revenue), a positive balance here means it's in debit (negative balance).
    opening_balance = opening_balance_query.scalar() or Decimal(0)

    # 2. Fetch Transactions directly from JournalItem for efficiency
    query = db.query(JournalItem).options(
        joinedload(JournalItem.journal_entry),
        joinedload(JournalItem.account)
    ).join(JournalEntry).filter(
        JournalEntry.tenant_id == tenant_id,
        JournalEntry.date >= start_date,
        JournalEntry.date <= end_date
    )

    # If filtering by account code, add the filter
    if account_code:
        query = query.join(ChartOfAccounts, JournalItem.account_id == ChartOfAccounts.id).filter(
            ChartOfAccounts.account_code == account_code
        )

    journal_items = query.order_by(JournalEntry.date, JournalEntry.id).all()

    # Pre-fetch IDs for POs and SOs to map numbers to IDs
    po_numbers = set()
    so_numbers = set()
    for item in journal_items:
        ref_doc = item.journal_entry.reference_document or ""
        if ref_doc.startswith("PO-"):
            parts = ref_doc.split("-")
            if len(parts) > 1 and parts[1].isdigit():
                po_numbers.add(int(parts[1]))
        elif ref_doc.startswith("SO-"):
            parts = ref_doc.split("-")
            if len(parts) > 1 and parts[1].isdigit():
                so_numbers.add(int(parts[1]))

    po_map = {}
    if po_numbers:
        pos = db.query(purchase_orders.PurchaseOrder.po_number, purchase_orders.PurchaseOrder.id).filter(
            purchase_orders.PurchaseOrder.tenant_id == tenant_id,
            purchase_orders.PurchaseOrder.po_number.in_(po_numbers)
        ).all()
        po_map = {p.po_number: str(p.id) for p in pos}

    so_map = {}
    if so_numbers:
        sos = db.query(sales_orders.SalesOrder.so_number, sales_orders.SalesOrder.id).filter(
            sales_orders.SalesOrder.tenant_id == tenant_id,
            sales_orders.SalesOrder.so_number.in_(so_numbers)
        ).all()
        so_map = {s.so_number: str(s.id) for s in sos}

    balance = opening_balance
    entries = []
    
    for item in journal_items:
        debit = item.debit
        credit = item.credit
        balance += (debit - credit)
        
        # Derive transaction type from reference_document prefix
        ref_doc = item.journal_entry.reference_document or ""
        
        ref_id = None
        if ref_doc.startswith("PO-"):
            t_type = "Purchase"
            parts = ref_doc.split("-")
            if len(parts) > 1 and parts[1].isdigit():
                ref_id = po_map.get(int(parts[1]))
        elif ref_doc.startswith("SO-"):
            t_type = "Sale"
            parts = ref_doc.split("-")
            if len(parts) > 1 and parts[1].isdigit():
                ref_id = so_map.get(int(parts[1]))
        elif ref_doc.startswith("USAGE-"):
            t_type = "Inventory Usage"
            parts = ref_doc.split("-")
            if len(parts) > 1:
                ref_id = parts[1]
        elif ref_doc.startswith("EXP-"):
            t_type = "Expense"
            parts = ref_doc.split("-")
            if len(parts) > 1:
                ref_id = parts[1]
        else:
            t_type = "Journal Entry"
            if "-" in ref_doc:
                parts = ref_doc.split("-", 1)
                if len(parts) == 2:
                    ref_id = parts[1]

        entries.append(GeneralLedgerEntry(
            date=item.journal_entry.date,
            transaction_type=t_type,
            party="", # Journal entries are generic, could fetch from reference doc if needed
            reference_document=item.journal_entry.reference_document,
            transaction_id=item.journal_entry.id,
            reference_id=ref_id,
            details=item.journal_entry.description,
            debit=debit,
            credit=credit,
            account_code=item.account.account_code,
            account_name=item.account.account_name,
            balance=balance
        ))

    report_title = "General Ledger"
    if account_code:
        report_title = f"General Ledger ({account_code})"

    # Create the GeneralLedger object and return it
    return GeneralLedger(
        title=report_title,
        opening_balance=opening_balance,
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
        non_deleted_payments = [p for p in po.payments if p.deleted_at is None]
        amount_paid = sum(Decimal(str(p.amount_paid)) for p in non_deleted_payments)
        balance_amount = Decimal(str(po.total_amount)) - amount_paid
        # Get the account code from the most recent payment if available
        account_code = None
        if non_deleted_payments:
            latest_payment = sorted(non_deleted_payments, key=lambda p: p.payment_date, reverse=True)[0]
            if latest_payment.account:
                account_code = latest_payment.account.account_code

        entries.append(PurchaseLedgerEntry(
            date=po.order_date,
            vendor_name=vendor.name,
            po_id=po.id,
            invoice_number=f"PO-{po.po_number}",
            description=po.notes,
            amount=Decimal(str(po.total_amount)),
            amount_paid=amount_paid,
            balance_amount=balance_amount,
            payment_status=po.status.value,
            account_code=account_code
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
        non_deleted_payments = [p for p in so.payments if p.deleted_at is None]
        amount_paid = sum(Decimal(str(p.amount_paid)) for p in non_deleted_payments)
        balance_amount = Decimal(str(so.total_amount)) - amount_paid
        # Get the account code from the most recent payment if available
        account_code = None
        if non_deleted_payments:
            latest_payment = sorted(non_deleted_payments, key=lambda p: p.payment_date, reverse=True)[0]
            if latest_payment.account:
                account_code = latest_payment.account.account_code

        entries.append(SalesLedgerEntry(
            date=so.order_date,
            customer_name=customer.name,
            so_id=so.id,
            invoice_number=f"SO-{so.so_number}",
            description=so.notes,
            amount=Decimal(str(so.total_amount)),
            amount_paid=amount_paid,
            balance_amount=balance_amount,
            payment_status=so.status.value,
            account_code=account_code
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
                    quantity_received = Decimal(str(report.table_received or 0)) + Decimal(str(report.jumbo_out or 0))
                    quantity_sold = Decimal(str(report.table_transfer or 0)) + Decimal(str(report.table_out or 0)) + Decimal(str(report.table_damage or 0))
                    quantity_on_hand = Decimal(str(report.table_closing or 0))
                elif "jumbo" in item.name.lower():
                    quantity_received = Decimal(str(report.jumbo_received or 0)) + Decimal(str(report.table_out or 0))
                    quantity_sold = Decimal(str(report.jumbo_transfer or 0)) + Decimal(str(report.jumbo_out or 0)) + Decimal(str(report.jumbo_waste or 0))
                    quantity_on_hand = Decimal(str(report.jumbo_closing or 0))
                elif "grade c" in item.name.lower():
                    quantity_received = Decimal(str(report.grade_c_shed_received or 0)) + Decimal(str(report.table_damage or 0))
                    quantity_sold = Decimal(str(report.grade_c_transfer or 0)) + Decimal(str(report.grade_c_labour or 0)) + Decimal(str(report.grade_c_waste or 0))
                    quantity_on_hand = Decimal(str(report.grade_c_closing or 0))
                
                # Only create an entry if there was some activity
                if quantity_received > 0 or quantity_sold > 0:
                    entries.append(InventoryLedgerEntry(
                        date=report.report_date,
                        reference=reference,
                        quantity_received=quantity_received,
                        unit_cost=Decimal(str(item.average_cost)),
                        total_cost=quantity_received * Decimal(str(item.average_cost)),
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
            "quantity_received": Decimal(str(pi.quantity)),
            "unit_cost": Decimal(str(pi.price_per_unit)),
            "total_cost": Decimal(str(pi.quantity)) * Decimal(str(pi.price_per_unit)),
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
            "quantity_sold": Decimal(str(si.quantity))
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
