from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
from decimal import Decimal
from database import get_db
from schemas.financial_settings import FinancialSettings, FinancialSettingsUpdate
from crud import financial_settings as crud_settings
from utils.tenancy import get_tenant_id
from utils.auth_utils import require_group, get_user_identifier
from models.journal_entry import JournalEntry
from models.journal_item import JournalItem
from models.chart_of_accounts import ChartOfAccounts
from schemas.journal_entry import JournalEntryCreate
from schemas.journal_item import JournalItemCreate
from crud import journal_entry as journal_entry_crud

router = APIRouter(
    prefix="/financial-settings",
    tags=["Financial Settings"],
)

@router.get("", response_model=FinancialSettings)
def get_settings(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    return crud_settings.get_financial_settings(db, tenant_id)

@router.patch("", response_model=FinancialSettings)
def update_settings(
    settings: FinancialSettingsUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_group(["admin"])),
    tenant_id: str = Depends(get_tenant_id)
):
    try:
        return crud_settings.update_financial_settings(db, settings, tenant_id, get_user_identifier(user))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/close-financial-year")
def close_financial_year(
    closing_date: date,
    db: Session = Depends(get_db),
    user: dict = Depends(require_group(["admin"])),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Closes the financial year. Zeros out P&L accounts and transfers net income to Retained Earnings.
    """
    settings = crud_settings.get_financial_settings(db, tenant_id)
    
    if not settings.retained_earnings_account_id:
        raise HTTPException(status_code=400, detail="Retained Earnings account is not configured in settings.")
        
    if settings.last_closed_date and closing_date <= settings.last_closed_date:
        raise HTTPException(status_code=400, detail=f"Closing date must be after the last closed date ({settings.last_closed_date}).")

    # 1. Fetch balances of all Income and Expense accounts up to the closing_date
    account_balances = db.query(
        ChartOfAccounts.id,
        ChartOfAccounts.account_type,
        func.sum(JournalItem.debit - JournalItem.credit).label("balance")
    ).join(
        JournalItem, JournalItem.account_id == ChartOfAccounts.id
    ).join(
        JournalEntry, JournalEntry.id == JournalItem.journal_entry_id
    ).filter(
        JournalEntry.tenant_id == tenant_id,
        JournalEntry.date <= closing_date,
        ChartOfAccounts.account_type.in_(["Revenue", "Expense"]) # Standard P&L types
    ).group_by(ChartOfAccounts.id, ChartOfAccounts.account_type).all()

    journal_items = []
    total_net_income = Decimal('0.00')

    # 2. Create offsetting entries to zero them out
    for acc_id, acc_type, balance in account_balances:
        if balance == 0:
            continue
            
        # Expenses normally have a positive (Debit) balance. To close, we Credit them.
        # Income normally has a negative (Credit) balance. To close, we Debit them.
        closing_debit = Decimal('0.00')
        closing_credit = Decimal('0.00')
        
        if balance > 0:
            closing_credit = Decimal(balance)
            total_net_income -= closing_credit # Deduct expenses from net income
        else:
            closing_debit = Decimal(abs(balance))
            total_net_income += closing_debit # Add income to net income
            
        if closing_debit > 0 or closing_credit > 0:
            journal_items.append(JournalItemCreate(account_id=acc_id, debit=closing_debit, credit=closing_credit))

    # 3. Post the balancing figure to Retained Earnings
    retained_debit = Decimal('0.00')
    retained_credit = Decimal('0.00')
    if total_net_income > 0:
        retained_credit = total_net_income # Profit increases equity (credit)
    elif total_net_income < 0:
        retained_debit = abs(total_net_income) # Loss decreases equity (debit)
        
    if retained_debit > 0 or retained_credit > 0:
        journal_items.append(JournalItemCreate(account_id=settings.retained_earnings_account_id, debit=retained_debit, credit=retained_credit))

    # 4. Create the Closing Journal Entry
    if journal_items:
        closing_entry = JournalEntryCreate(
            date=closing_date,
            description=f"Year-End Closing Entry for {closing_date.year}",
            items=journal_items
        )
        journal_entry_crud.create_journal_entry(db=db, entry=closing_entry, tenant_id=tenant_id)

    # 5. Update the last closed date to lock the period
    # Re-fetch the settings object because the db.commit() inside create_journal_entry expired the session
    settings = crud_settings.get_financial_settings(db, tenant_id)
    settings.last_closed_date = closing_date 
    db.add(settings)
    db.commit()

    return {"message": "Financial year closed successfully.", "net_income_transferred": total_net_income}


@router.post("/reopen-financial-year")
def reopen_financial_year(
    db: Session = Depends(get_db),
    user: dict = Depends(require_group(["admin"])),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Reopens the most recently closed financial year by deleting the closing journal entry.
    """
    settings = crud_settings.get_financial_settings(db, tenant_id)
    
    if not settings.last_closed_date:
        raise HTTPException(status_code=400, detail="No financial year is currently closed.")

    # Find the automated closing entry for the locked date
    closing_entry = db.query(JournalEntry).filter(
        JournalEntry.tenant_id == tenant_id,
        JournalEntry.date == settings.last_closed_date,
        JournalEntry.description.like("Year-End Closing Entry%")
    ).first()

    # Find the next most recent year-end closing entry to revert the last_closed_date to
    previous_closing = db.query(JournalEntry).filter(
        JournalEntry.tenant_id == tenant_id,
        JournalEntry.description.like("Year-End Closing Entry%"),
        JournalEntry.date < settings.last_closed_date
    ).order_by(JournalEntry.date.desc()).first()

    if closing_entry:
        # Rely on SQLAlchemy's cascade delete defined on the relationship
        db.delete(closing_entry)

    settings.last_closed_date = previous_closing.date if previous_closing else None
    db.add(settings)
    db.commit()

    return {"message": "Financial year reopened successfully. Period is unlocked."}