import sys
import os
from decimal import Decimal
import logging
from dotenv import load_dotenv

load_dotenv()

# Add the parent directory to sys.path to allow imports from backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, joinedload
from database import engine
from models.financial_settings import FinancialSettings
from models.chart_of_accounts import ChartOfAccounts
from models.payments import Payment
from models.sales_payments import SalesPayment
from models.operational_expenses import OperationalExpense
from models.composition_usage_history import CompositionUsageHistory
from models.journal_entry import JournalEntry
from models.journal_item import JournalItem
from models.purchase_orders import PurchaseOrder
from models.sales_order_items import SalesOrderItem
from models.sales_orders import SalesOrder
from models.inventory_items import InventoryItem
from models.composition_usage_item import CompositionUsageItem
from crud.financial_settings import get_financial_settings

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("migration")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def migrate():
    db = SessionLocal()
    try:
        # 1. Identify all Tenants
        tenant_ids = set()
        # Broaden tenant discovery to include POs and SOs
        for model in [PurchaseOrder, SalesOrder, Payment, SalesPayment, OperationalExpense, CompositionUsageHistory]:
            tenants = db.query(model.tenant_id).distinct().all()
            for t in tenants:
                if t[0]: tenant_ids.add(t[0])
        
        logger.info(f"Found tenants to migrate: {list(tenant_ids)}")

        for tenant_id in tenant_ids:
            logger.info(f"--- Processing Tenant: {tenant_id} ---")
            
            # Ensure settings exist (this will seed accounts if missing)
            settings = get_financial_settings(db, tenant_id)
            if not all([
                settings,
                settings.default_inventory_account_id,
                settings.default_accounts_payable_account_id,
                settings.default_cash_account_id,
                settings.default_cogs_account_id,
                settings.default_accounts_receivable_account_id,
                settings.default_sales_account_id,
                settings.default_operational_expense_account_id
            ]):
                logger.error(f"Could not initialize all required default accounts for tenant {tenant_id}. Skipping.")
                continue

            # --- 0. Clear all existing journal entries for the tenant ---
            logger.info(f"Deleting existing journal entries for tenant {tenant_id}...")
            db.query(JournalItem).filter(JournalItem.tenant_id == tenant_id).delete(synchronize_session=False)
            db.query(JournalEntry).filter(JournalEntry.tenant_id == tenant_id).delete(synchronize_session=False)
            db.flush()
            logger.info("Deletion complete.")

            # --- 1. Migrate Purchase Orders (Goods Receipt) ---
            purchase_orders = db.query(PurchaseOrder).filter(PurchaseOrder.tenant_id == tenant_id).all()
            for po in purchase_orders:
                if po.total_amount > 0:
                    je = JournalEntry(
                        tenant_id=tenant_id,
                        date=po.order_date,
                        description=f"Purchase Order PO-{po.po_number}",
                        reference_document=f"PO-{po.po_number}"
                    )
                    db.add(je)
                    db.flush()
                    
                    # Debit Inventory, Credit Accounts Payable
                    db.add(JournalItem(tenant_id=tenant_id, journal_entry_id=je.id, account_id=settings.default_inventory_account_id, debit=po.total_amount, credit=0))
                    db.add(JournalItem(tenant_id=tenant_id, journal_entry_id=je.id, account_id=settings.default_accounts_payable_account_id, debit=0, credit=po.total_amount))
                    logger.info(f"Created JE for Purchase Order {po.id} (Goods Receipt)")

            # --- 2. Migrate Purchase Payments ---
            payments = db.query(Payment).options(joinedload(Payment.purchase_order)).filter(Payment.tenant_id == tenant_id).all()
            for payment in payments:
                po = payment.purchase_order
                if not po: continue
                
                credit_account_id = settings.default_cash_account_id
                
                je = JournalEntry(
                    tenant_id=tenant_id,
                    date=payment.payment_date,
                    description=f"Payment for Purchase Order PO-{po.po_number}",
                    reference_document=f"PO-{po.po_number}"
                )
                db.add(je)
                db.flush()
                
                # Debit Accounts Payable, Credit Cash
                db.add(JournalItem(tenant_id=tenant_id, journal_entry_id=je.id, account_id=settings.default_accounts_payable_account_id, debit=payment.amount_paid, credit=0))
                db.add(JournalItem(tenant_id=tenant_id, journal_entry_id=je.id, account_id=credit_account_id, debit=0, credit=payment.amount_paid))
                logger.info(f"Created JE for Purchase Payment {payment.id}")

            # --- 3. Migrate Sales Orders (Revenue & COGS) ---
            sales_orders = db.query(SalesOrder).options(joinedload(SalesOrder.items).joinedload(SalesOrderItem.inventory_item)).filter(SalesOrder.tenant_id == tenant_id).all()
            for so in sales_orders:
                # WARNING: This calculation uses the CURRENT average_cost of the inventory item,
                # which may not reflect the historical cost at the time of the sale.
                # This is a limitation of the current data model.
                # Calculate COGS for sales orders, excluding eggs
                # Egg costs are tracked through composition usage
                total_cost_of_goods = Decimal(0)
                for item in so.items:
                    if item.inventory_item:
                        # Skip eggs in COGS calculation as they're tracked through composition usage
                        if item.inventory_item.name not in ["Table Egg", "Jumbo Egg", "Grade C Egg"]:
                            total_cost_of_goods += item.quantity * (item.inventory_item.average_cost or Decimal(0))

                # 3a. Revenue Entry (Invoice)
                if so.total_amount > 0:
                    je_rev = JournalEntry(
                        tenant_id=tenant_id,
                        date=so.order_date,
                        description=f"Invoice for Sales Order SO-{so.so_number}",
                        reference_document=f"SO-{so.so_number}"
                    )
                    db.add(je_rev)
                    db.flush()
                    # Debit AR, Credit Sales
                    db.add(JournalItem(tenant_id=tenant_id, journal_entry_id=je_rev.id, account_id=settings.default_accounts_receivable_account_id, debit=so.total_amount, credit=0))
                    db.add(JournalItem(tenant_id=tenant_id, journal_entry_id=je_rev.id, account_id=settings.default_sales_account_id, debit=0, credit=so.total_amount))

                # 3b. COGS Entry
                if total_cost_of_goods > 0:
                    je = JournalEntry(
                        tenant_id=tenant_id,
                        date=so.order_date,
                        description=f"COGS for Sales Order SO-{so.so_number}",
                        reference_document=f"SO-{so.so_number}"
                    )
                    db.add(je)
                    db.flush()

                    # Debit COGS, Credit Inventory
                    db.add(JournalItem(tenant_id=tenant_id, journal_entry_id=je.id, account_id=settings.default_cogs_account_id, debit=total_cost_of_goods, credit=0))
                    db.add(JournalItem(tenant_id=tenant_id, journal_entry_id=je.id, account_id=settings.default_inventory_account_id, debit=0, credit=total_cost_of_goods))
                    logger.info(f"Created JE for Sales Order {so.id} (COGS)")

            # --- 4. Migrate Sales Payments (Revenue) ---
            sales_payments = db.query(SalesPayment).options(joinedload(SalesPayment.sales_order)).filter(SalesPayment.tenant_id == tenant_id).all()
            for sp in sales_payments:
                so = sp.sales_order
                if not so: continue

                debit_account_id = settings.default_cash_account_id

                je = JournalEntry(
                    tenant_id=tenant_id,
                    date=sp.payment_date,
                    description=f"Payment for Sales Order SO-{so.so_number}",
                    reference_document=f"SO-{so.so_number}"
                )
                db.add(je)
                db.flush()

                # Debit Cash, Credit Accounts Receivable
                db.add(JournalItem(tenant_id=tenant_id, journal_entry_id=je.id, account_id=debit_account_id, debit=sp.amount_paid, credit=0))
                db.add(JournalItem(tenant_id=tenant_id, journal_entry_id=je.id, account_id=settings.default_accounts_receivable_account_id, debit=0, credit=sp.amount_paid))
                logger.info(f"Created JE for Sales Payment {sp.id}")

            # --- 5. Migrate Operational Expenses ---
            expenses = db.query(OperationalExpense).filter(OperationalExpense.tenant_id == tenant_id).all()
            for exp in expenses:
                credit_account_id = settings.default_cash_account_id
                
                # Find Debit Account (Expense)
                debit_account = db.query(ChartOfAccounts).filter(
                    ChartOfAccounts.account_name == exp.expense_type,
                    ChartOfAccounts.account_type == 'Expense',
                    ChartOfAccounts.tenant_id == tenant_id
                ).first()
                debit_account_id = debit_account.id if debit_account else settings.default_operational_expense_account_id

                if not debit_account_id:
                    logger.warning(f"Skipping Expense {exp.id}: No suitable expense account found.")
                    continue

                je = JournalEntry(
                    tenant_id=tenant_id,
                    date=exp.expense_date.date(),
                    description=f"Operational Expense: {exp.expense_type}",
                    reference_document=f"EXP-{exp.id}"
                )
                db.add(je)
                db.flush()

                # Debit Expense, Credit Cash
                db.add(JournalItem(tenant_id=tenant_id, journal_entry_id=je.id, account_id=debit_account_id, debit=exp.amount, credit=0))
                db.add(JournalItem(tenant_id=tenant_id, journal_entry_id=je.id, account_id=credit_account_id, debit=0, credit=exp.amount))
                logger.info(f"Created JE for Expense {exp.id}")

            # --- 6. Migrate COGS (Composition Usage) ---
            usages = db.query(CompositionUsageHistory).options(joinedload(CompositionUsageHistory.items).joinedload(CompositionUsageItem.inventory_item)).filter(CompositionUsageHistory.tenant_id == tenant_id).all()
            for usage in usages:
                # WARNING: This calculation uses the CURRENT average_cost of the inventory item,
                # which may not reflect the historical cost at the time of the usage.
                # This is a limitation of the current data model.
                total_cost = Decimal(0)
                for item in usage.items:
                    if item.inventory_item:
                        quantity_used = Decimal(item.weight) * Decimal(usage.times)
                        cost = quantity_used * (item.inventory_item.average_cost or Decimal(0))
                        total_cost += cost
                
                if total_cost > 0:
                    je = JournalEntry(
                        tenant_id=tenant_id,
                        date=usage.used_at,
                        description=f"COGS for Composition Usage #{usage.id} ({usage.composition_name})",
                        reference_document=f"USAGE-{usage.id}"
                    )
                    db.add(je)
                    db.flush()

                    # Debit COGS, Credit Inventory
                    db.add(JournalItem(tenant_id=tenant_id, journal_entry_id=je.id, account_id=settings.default_cogs_account_id, debit=total_cost, credit=0))
                    db.add(JournalItem(tenant_id=tenant_id, journal_entry_id=je.id, account_id=settings.default_inventory_account_id, debit=0, credit=total_cost))
                    logger.info(f"Created JE for Usage {usage.id}")

            db.commit()
            logger.info(f"--- Migration completed for tenant {tenant_id} ---")

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate()