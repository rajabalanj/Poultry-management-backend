from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from schemas import operational_expenses as schemas
from crud import operational_expenses as crud
from utils.tenancy import get_tenant_id
from utils.auth_utils import get_current_user, get_user_identifier

# Imports for Journal Entry
import logging
from decimal import Decimal
from crud import journal_entry as journal_entry_crud
from schemas.journal_entry import JournalEntryCreate
from schemas.journal_item import JournalItemCreate
from models.chart_of_accounts import ChartOfAccounts
from crud.financial_settings import get_financial_settings

router = APIRouter(
    prefix="/operational-expenses",
    tags=["Operational Expenses"],
)

logger = logging.getLogger("operational_expenses")

@router.post("/", response_model=schemas.OperationalExpense)
def create_operational_expense(expense: schemas.OperationalExpenseCreate, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id), user: dict = Depends(get_current_user)):
    user_id = get_user_identifier(user)
    db_expense = crud.create_operational_expense(db=db, expense=expense, tenant_id=tenant_id, user_id=user_id)

    # --- Create Journal Entry for the Operational Expense ---
    try:
        settings = get_financial_settings(db, tenant_id)
        
        # 1. Find the Credit Account (Cash/Bank) - use default from financial settings
        credit_account_id = settings.default_cash_account_id

        if not credit_account_id:
             logger.error(f"No default Cash account configured. Journal entry skipped.")
             return db_expense

        # 2. Find the Debit Account (The Expense account)
        # Try to find an account matching the expense_type name
        debit_account = db.query(ChartOfAccounts).filter(
            ChartOfAccounts.account_name == db_expense.expense_type,
            ChartOfAccounts.account_type == 'Expense',
            ChartOfAccounts.tenant_id == tenant_id
        ).first()

        debit_account_id = debit_account.id if debit_account else settings.default_operational_expense_account_id

        if not debit_account_id:
            logger.error(f"Expense account named '{db_expense.expense_type}' not found and no default Operational Expense account configured. Journal entry skipped.")
            return db_expense

        # 3. Create the journal entry
        # Round amount to 2 decimal places to match journal entry requirements
        rounded_amount = db_expense.amount.quantize(Decimal('0.01'))
        
        journal_items = [
            JournalItemCreate(account_id=debit_account_id, debit=rounded_amount, credit=Decimal('0.0')),
            JournalItemCreate(account_id=credit_account_id, debit=Decimal('0.0'), credit=rounded_amount)
        ]

        expense_date = db_expense.expense_date if isinstance(db_expense.expense_date, date) else db_expense.expense_date.date()

        journal_entry_schema = JournalEntryCreate(
            date=expense_date,
            description=f"Operational Expense: {db_expense.expense_type}",
            items=journal_items
        )
        journal_entry_crud.create_journal_entry(db=db, entry=journal_entry_schema, tenant_id=tenant_id)
        logger.info(f"Journal entry created for operational expense {db_expense.id}")

    except Exception as e:
        logger.error(f"Failed to create journal entry for operational expense {db_expense.id}: {e}")
    # --- End Journal Entry ---

    return db_expense

@router.get("/", response_model=List[schemas.OperationalExpense])
def read_operational_expenses(start_date: date, end_date: date, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    return crud.get_operational_expenses_by_date_range(db=db, start_date=start_date, end_date=end_date, tenant_id=tenant_id)

@router.get("/{expense_id}", response_model=schemas.OperationalExpense)
def read_operational_expense(expense_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    db_expense = crud.get_operational_expense(db=db, expense_id=expense_id, tenant_id=tenant_id)
    if db_expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return db_expense

@router.put("/{expense_id}", response_model=schemas.OperationalExpense)
def update_operational_expense(expense_id: int, expense: schemas.OperationalExpenseUpdate, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id), user: dict = Depends(get_current_user)):
    user_id = get_user_identifier(user)
    db_expense = crud.update_operational_expense(db=db, expense_id=expense_id, expense=expense, tenant_id=tenant_id, user_id=user_id)
    if db_expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return db_expense

@router.delete("/{expense_id}")
def delete_operational_expense(expense_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id), user: dict = Depends(get_current_user)):
    user_id = get_user_identifier(user)
    db_expense = crud.get_operational_expense(db=db, expense_id=expense_id, tenant_id=tenant_id)
    if db_expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    crud.delete_operational_expense(db=db, expense_id=expense_id, tenant_id=tenant_id, user_id=user_id)
    return {"message": "Expense deleted successfully"}
