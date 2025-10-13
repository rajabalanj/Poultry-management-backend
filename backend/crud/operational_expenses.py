from sqlalchemy.orm import Session
from crud.audit_log import create_audit_log
from schemas.audit_log import AuditLogCreate
from utils import sqlalchemy_to_dict
from models import operational_expenses as models
from schemas import operational_expenses as schemas
from datetime import date
from typing import List
import datetime
import pytz

def get_operational_expense(db: Session, expense_id: int, tenant_id: int):
    return db.query(models.OperationalExpense).filter(models.OperationalExpense.id == expense_id, models.OperationalExpense.tenant_id == tenant_id).first()

def get_operational_expenses_by_date_range(db: Session, start_date: date, end_date: date, tenant_id: int) -> List[models.OperationalExpense]:
    return db.query(models.OperationalExpense).filter(
        models.OperationalExpense.tenant_id == tenant_id,
        models.OperationalExpense.date >= start_date,
        models.OperationalExpense.date <= end_date
    ).all()

def create_operational_expense(db: Session, expense: schemas.OperationalExpenseCreate, tenant_id: int, user_id: str):
    db_expense = models.OperationalExpense(**expense.model_dump(), tenant_id=tenant_id, created_by=user_id)
    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense

def update_operational_expense(db: Session, expense_id: int, expense: schemas.OperationalExpenseUpdate, tenant_id: int, user_id: str):
    db_expense = get_operational_expense(db, expense_id, tenant_id)
    if db_expense:
        old_values = sqlalchemy_to_dict(db_expense)
        for key, value in expense.model_dump().items():
            setattr(db_expense, key, value)
        db_expense.updated_by = user_id
        new_values = sqlalchemy_to_dict(db_expense)
        log_entry = AuditLogCreate(
            table_name='operational_expenses',
            record_id=str(expense_id),
            changed_by=user_id,
            action='UPDATE',
            old_values=old_values,
            new_values=new_values
        )
        create_audit_log(db=db, log_entry=log_entry)
        db.commit()
        db.refresh(db_expense)
    return db_expense

def delete_operational_expense(db: Session, expense_id: int, tenant_id: int, user_id: str = None):
    db_expense = get_operational_expense(db, expense_id, tenant_id)
    if db_expense:
        old_values = sqlalchemy_to_dict(db_expense)
        # Soft-delete
        db_expense.deleted_at = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
        db_expense.deleted_by = user_id
        db.add(db_expense)
        db.commit()
        db.refresh(db_expense)

        # Audit log for deletion
        try:
            new_values = sqlalchemy_to_dict(db_expense)
            log_entry = AuditLogCreate(
                table_name='operational_expenses',
                record_id=str(expense_id),
                changed_by=user_id,
                action='DELETE',
                old_values=old_values or {},
                new_values=new_values or {}
            )
            create_audit_log(db=db, log_entry=log_entry)
        except Exception:
            pass

    return db_expense
