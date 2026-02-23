
from sqlalchemy.orm import Session
from models import chart_of_accounts as chart_of_accounts_model
from schemas.chart_of_accounts import ChartOfAccountsCreate, ChartOfAccountsUpdate

def get_account_by_code(db: Session, account_code: str, tenant_id: str):
    return db.query(chart_of_accounts_model.ChartOfAccounts).filter(
        chart_of_accounts_model.ChartOfAccounts.account_code == account_code,
        chart_of_accounts_model.ChartOfAccounts.tenant_id == tenant_id
    ).first()

def get_accounts(db: Session, tenant_id: str, account_type: str = None, skip: int = 0, limit: int = 100):
    query = db.query(chart_of_accounts_model.ChartOfAccounts).filter(
        chart_of_accounts_model.ChartOfAccounts.tenant_id == tenant_id,
        chart_of_accounts_model.ChartOfAccounts.is_active == True
    )

    if account_type:
        query = query.filter(chart_of_accounts_model.ChartOfAccounts.account_type == account_type)

    return query.offset(skip).limit(limit).all()

def create_account(db: Session, account: ChartOfAccountsCreate, tenant_id: str):
    db_account = chart_of_accounts_model.ChartOfAccounts(**account.dict(), tenant_id=tenant_id)
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    return db_account

def update_account(db: Session, account_code: str, account_update: ChartOfAccountsUpdate, tenant_id: str):
    db_account = get_account_by_code(db, account_code, tenant_id)
    if not db_account:
        return None

    update_data = account_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_account, key, value)

    db.commit()
    db.refresh(db_account)
    return db_account

def delete_account(db: Session, account_code: str, tenant_id: str):
    db_account = get_account_by_code(db, account_code, tenant_id)
    if not db_account:
        return False

    # Soft delete by setting is_active to False
    db_account.is_active = False
    db.commit()
    return True

def initialize_default_accounts(db: Session, tenant_id: str):
    """Initialize default chart of accounts for a new tenant"""
    default_accounts = [
        {"account_code": "1000", "account_name": "Cash", "account_type": "Asset"},
        {"account_code": "1100", "account_name": "Accounts Receivable", "account_type": "Asset"},
        {"account_code": "1200", "account_name": "Inventory", "account_type": "Asset"},
        {"account_code": "2000", "account_name": "Accounts Payable", "account_type": "Liability"},
        {"account_code": "3000", "account_name": "Owner's Equity", "account_type": "Equity"},
        {"account_code": "4000", "account_name": "Sales Revenue", "account_type": "Revenue"},
        {"account_code": "5000", "account_name": "Cost of Goods Sold", "account_type": "Expense"},
        {"account_code": "6000", "account_name": "Operating Expenses", "account_type": "Expense"},
    ]

    for account_data in default_accounts:
        existing = get_account_by_code(db, account_data["account_code"], tenant_id)
        if not existing:
            create_account(db, ChartOfAccountsCreate(**account_data), tenant_id)

    return True
