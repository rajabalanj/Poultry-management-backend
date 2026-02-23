from sqlalchemy.orm import Session
from models.financial_settings import FinancialSettings
from models.chart_of_accounts import ChartOfAccounts
from schemas.financial_settings import FinancialSettingsUpdate
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

def get_or_create_account(db: Session, tenant_id: str, name: str, code: str, type: str) -> ChartOfAccounts:
    """Helper to find an account by name/code or create it if missing."""
    # Try finding by name first
    account = db.query(ChartOfAccounts).filter(
        ChartOfAccounts.account_name == name,
        ChartOfAccounts.tenant_id == tenant_id
    ).first()
    
    if not account:
        # Try finding by code
        account = db.query(ChartOfAccounts).filter(
            ChartOfAccounts.account_code == code,
            ChartOfAccounts.tenant_id == tenant_id
        ).first()

    if not account:
        logger.info(f"Seeding default account '{name}' ({code}) for tenant {tenant_id}")
        account = ChartOfAccounts(
            tenant_id=tenant_id,
            account_code=code,
            account_name=name,
            account_type=type,
            is_active=True,
            description=f"Default {name} account"
        )
        db.add(account)
        db.commit()
        db.refresh(account)
    
    return account

def get_financial_settings(db: Session, tenant_id: str) -> FinancialSettings:
    settings = db.query(FinancialSettings).filter(FinancialSettings.tenant_id == tenant_id).first()
    
    if not settings:
        logger.info(f"No financial settings found for tenant {tenant_id}. Initializing defaults.")
        
        # Seed Default Accounts
        cash_acc = get_or_create_account(db, tenant_id, "Cash", "1000", "Asset")
        sales_acc = get_or_create_account(db, tenant_id, "Sales", "4000", "Revenue")
        inv_acc = get_or_create_account(db, tenant_id, "Inventory", "1200", "Asset")
        cogs_acc = get_or_create_account(db, tenant_id, "Cost of Goods Sold", "5000", "Expense")
        op_exp_acc = get_or_create_account(db, tenant_id, "Operational Expense", "6000", "Expense")
        ap_acc = get_or_create_account(db, tenant_id, "Accounts Payable", "2000", "Liability")
        ar_acc = get_or_create_account(db, tenant_id, "Accounts Receivable", "1100", "Asset")

        settings = FinancialSettings(
            tenant_id=tenant_id,
            default_cash_account_id=cash_acc.id,
            default_sales_account_id=sales_acc.id,
            default_inventory_account_id=inv_acc.id,
            default_cogs_account_id=cogs_acc.id,
            default_operational_expense_account_id=op_exp_acc.id,
            default_accounts_payable_account_id=ap_acc.id,
            default_accounts_receivable_account_id=ar_acc.id,
            is_initialized=True
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    else:
        # Check for missing fields in existing settings (e.g. from migrations) and backfill them
        updated = False
        if not settings.default_accounts_payable_account_id:
            ap_acc = get_or_create_account(db, tenant_id, "Accounts Payable", "2000", "Liability")
            settings.default_accounts_payable_account_id = ap_acc.id
            updated = True
        if not settings.default_accounts_receivable_account_id:
            ar_acc = get_or_create_account(db, tenant_id, "Accounts Receivable", "1100", "Asset")
            settings.default_accounts_receivable_account_id = ar_acc.id
            updated = True
        
        # Ensure other fields are present too (robustness against partial data)
        if not settings.default_cash_account_id:
            cash_acc = get_or_create_account(db, tenant_id, "Cash", "1000", "Asset")
            settings.default_cash_account_id = cash_acc.id
            updated = True
        if not settings.default_sales_account_id:
            sales_acc = get_or_create_account(db, tenant_id, "Sales", "4000", "Revenue")
            settings.default_sales_account_id = sales_acc.id
            updated = True
        if not settings.default_inventory_account_id:
            inv_acc = get_or_create_account(db, tenant_id, "Inventory", "1200", "Asset")
            settings.default_inventory_account_id = inv_acc.id
            updated = True
        if not settings.default_cogs_account_id:
            cogs_acc = get_or_create_account(db, tenant_id, "Cost of Goods Sold", "5000", "Expense")
            settings.default_cogs_account_id = cogs_acc.id
            updated = True
        if not settings.default_operational_expense_account_id:
            op_exp_acc = get_or_create_account(db, tenant_id, "Operational Expense", "6000", "Expense")
            settings.default_operational_expense_account_id = op_exp_acc.id
            updated = True

        if updated:
            settings.is_initialized = True
            db.commit()
            db.refresh(settings)
    
    return settings

def update_financial_settings(db: Session, settings_update: FinancialSettingsUpdate, tenant_id: str, user_id: str) -> FinancialSettings:
    settings = get_financial_settings(db, tenant_id)
    
    # Prevent updates after initialization
    if settings.is_initialized:
        raise ValueError(
            "Financial settings are locked after initialization. "
            "Default accounts cannot be changed after the first setup to ensure data integrity and accurate financial reports."
        )
    
    update_data = settings_update.model_dump(exclude_unset=True)

    # Define expected account types for validation
    expected_types = {
        'default_cash_account_id': 'Asset',
        'default_sales_account_id': 'Revenue',
        'default_inventory_account_id': 'Asset',
        'default_cogs_account_id': 'Expense',
        'default_operational_expense_account_id': 'Expense',
        'default_accounts_payable_account_id': 'Liability',
        'default_accounts_receivable_account_id': 'Asset'
    }
    
    # Validate that accounts belong to the tenant if they are being updated
    for field, account_id in update_data.items():
        if account_id is not None:
            account = db.query(ChartOfAccounts).filter(
                ChartOfAccounts.id == account_id,
                ChartOfAccounts.tenant_id == tenant_id
            ).first()
            if not account:
                raise ValueError(f"Account ID {account_id} not found for this tenant.")
            
            # Validate account type
            if field in expected_types:
                expected_type = expected_types[field]
                if account.account_type != expected_type:
                    raise ValueError(f"Account for '{field}' must be of type '{expected_type}', but got '{account.account_type}'.")

    for key, value in update_data.items():
        setattr(settings, key, value)

    settings.updated_by = user_id
    settings.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))

    db.commit()
    db.refresh(settings)
    return settings