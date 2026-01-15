from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from schemas.financial_reports import ProfitAndLoss, BalanceSheet, FinancialSummary
from schemas.ledgers import GeneralLedger, PurchaseLedger, SalesLedger, InventoryLedger
from crud import financial_reports as crud_financial_reports
from crud import financial_summary as crud_financial_summary
from datetime import date
from typing import Optional
from utils.tenancy import get_tenant_id

router = APIRouter(
    prefix="/financial-reports",
    tags=["Financial Reports"],
)

@router.get("/financial-summary", response_model=FinancialSummary)
def get_financial_summary(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    return crud_financial_summary.get_financial_summary(
        db=db,
        start_date=start_date,
        end_date=end_date,
        tenant_id=tenant_id
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


@router.get("/general-ledger", response_model=GeneralLedger)
def get_general_ledger(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type", enum=["purchase", "sales"])
):
    return crud_financial_reports.get_general_ledger(db=db, start_date=start_date, end_date=end_date, tenant_id=tenant_id, transaction_type=transaction_type)

@router.get("/subsidiary-ledger/purchases/{vendor_id}", response_model=PurchaseLedger)
def get_purchase_ledger(
    vendor_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    return crud_financial_reports.get_purchase_ledger(db=db, vendor_id=vendor_id, tenant_id=tenant_id)

@router.get("/subsidiary-ledger/sales/{customer_id}", response_model=SalesLedger)
def get_sales_ledger(
    customer_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    return crud_financial_reports.get_sales_ledger(db=db, customer_id=customer_id, tenant_id=tenant_id)

@router.get("/subsidiary-ledger/inventory/{item_id}", response_model=InventoryLedger)
def get_inventory_ledger(
    item_id: int,
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    return crud_financial_reports.get_inventory_ledger(db=db, item_id=item_id, start_date=start_date, end_date=end_date, tenant_id=tenant_id)
