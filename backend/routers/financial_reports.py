from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from schemas.financial_reports import ProfitAndLoss, BalanceSheet
from crud import financial_reports as crud_financial_reports
from datetime import date
from utils.tenancy import get_tenant_id

router = APIRouter(
    prefix="/financial-reports",
    tags=["Financial Reports"],
)

@router.get("/profit-and-loss", response_model=ProfitAndLoss)
def get_profit_and_loss(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    return crud_financial_reports.get_profit_and_loss(
        db=db, 
        start_date=start_date, 
        end_date=end_date, 
        tenant_id=tenant_id
    )

@router.get("/balance-sheet", response_model=BalanceSheet)
def get_balance_sheet(
    as_of_date: date,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    return crud_financial_reports.get_balance_sheet(db=db, as_of_date=as_of_date, tenant_id=tenant_id)
