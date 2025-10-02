from sqlalchemy.orm import Session
from models import operational_expenses as models
from schemas import operational_expenses as schemas
from datetime import date
from typing import List

def get_operational_expense(db: Session, expense_id: int, tenant_id: int):
    return db.query(models.OperationalExpense).filter(models.OperationalExpense.id == expense_id, models.OperationalExpense.tenant_id == tenant_id).first()

def get_operational_expenses_by_date_range(db: Session, start_date: date, end_date: date, tenant_id: int) -> List[models.OperationalExpense]:
    return db.query(models.OperationalExpense).filter(
        models.OperationalExpense.tenant_id == tenant_id,
        models.OperationalExpense.date >= start_date,
        models.OperationalExpense.date <= end_date
    ).all()

def create_operational_expense(db: Session, expense: schemas.OperationalExpenseCreate, tenant_id: int):
    db_expense = models.OperationalExpense(**expense.model_dump(), tenant_id=tenant_id)
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense

def update_operational_expense(db: Session, expense_id: int, expense: schemas.OperationalExpenseUpdate, tenant_id: int):
    db_expense = get_operational_expense(db, expense_id, tenant_id)
    if db_expense:
        for key, value in expense.model_dump().items():
            setattr(db_expense, key, value)
        db.commit()
        db.refresh(db_expense)
    return db_expense

def delete_operational_expense(db: Session, expense_id: int, tenant_id: int):
    db_expense = get_operational_expense(db, expense_id, tenant_id)
    if db_expense:
        db.delete(db_expense)
        db.commit()
    return db_expense
