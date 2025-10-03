from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from schemas import operational_expenses as schemas
from crud import operational_expenses as crud
from utils.tenancy import get_tenant_id

router = APIRouter(
    prefix="/operational-expenses",
    tags=["Operational Expenses"],
)

@router.post("/", response_model=schemas.OperationalExpense)
def create_operational_expense(expense: schemas.OperationalExpenseCreate, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    return crud.create_operational_expense(db=db, expense=expense, tenant_id=tenant_id)

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
def update_operational_expense(expense_id: int, expense: schemas.OperationalExpenseUpdate, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    db_expense = crud.update_operational_expense(db=db, expense_id=expense_id, expense=expense, tenant_id=tenant_id)
    if db_expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return db_expense

@router.delete("/{expense_id}", response_model=schemas.OperationalExpense)
def delete_operational_expense(expense_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    db_expense = crud.delete_operational_expense(db=db, expense_id=expense_id, tenant_id=tenant_id)
    if db_expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return db_expense
