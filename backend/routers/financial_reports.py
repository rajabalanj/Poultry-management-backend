from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import get_db
import os
from schemas.financial_reports import ProfitAndLoss, BalanceSheet, FinancialSummary
from schemas.ledgers import GeneralLedger, PurchaseLedger, SalesLedger, InventoryLedger
from crud import financial_reports as crud_financial_reports
from crud import financial_summary as crud_financial_summary
from datetime import date
from typing import Optional
from utils.tenancy import get_tenant_id
from utils.receipt_utils import (
    generate_profit_and_loss_pdf,
    generate_balance_sheet_pdf,
    generate_financial_summary_pdf,
    generate_general_ledger_pdf,
    generate_purchase_sales_ledger_pdf,
    generate_inventory_ledger_pdf
)

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

@router.get("/financial-summary/export")
def export_financial_summary(
    start_date: date,
    end_date: date,
    background_tasks: BackgroundTasks,
    export_format: str = Query("pdf", alias="format", description="Export format"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    if export_format.lower() != "pdf":
        raise HTTPException(status_code=400, detail="Only PDF format is currently supported")
    
    data = crud_financial_summary.get_financial_summary(db=db, start_date=start_date, end_date=end_date, tenant_id=tenant_id)
    filepath = generate_financial_summary_pdf(data, start_date, end_date, db, tenant_id)
    background_tasks.add_task(os.remove, filepath)
    return FileResponse(path=filepath, filename=f"financial_summary_{start_date}_{end_date}.pdf", media_type="application/pdf")

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

@router.get("/profit-and-loss/export")
def export_profit_and_loss(
    start_date: date,
    end_date: date,
    background_tasks: BackgroundTasks,
    export_format: str = Query("pdf", alias="format", description="Export format"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    if export_format.lower() != "pdf":
        raise HTTPException(status_code=400, detail="Only PDF format is currently supported")
    
    data = crud_financial_reports.get_profit_and_loss(db=db, start_date=start_date, end_date=end_date, tenant_id=tenant_id)
    filepath = generate_profit_and_loss_pdf(data, start_date, end_date, db, tenant_id)
    background_tasks.add_task(os.remove, filepath)
    return FileResponse(path=filepath, filename=f"profit_and_loss_{start_date}_{end_date}.pdf", media_type="application/pdf")

@router.get("/balance-sheet", response_model=BalanceSheet)
def get_balance_sheet(
    as_of_date: date,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    return crud_financial_reports.get_balance_sheet(db=db, as_of_date=as_of_date, tenant_id=tenant_id)

@router.get("/balance-sheet/export")
def export_balance_sheet(
    as_of_date: date,
    background_tasks: BackgroundTasks,
    export_format: str = Query("pdf", alias="format", description="Export format"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    if export_format.lower() != "pdf":
        raise HTTPException(status_code=400, detail="Only PDF format is currently supported")
    
    data = crud_financial_reports.get_balance_sheet(db=db, as_of_date=as_of_date, tenant_id=tenant_id)
    filepath = generate_balance_sheet_pdf(data, as_of_date, db, tenant_id)
    background_tasks.add_task(os.remove, filepath)
    return FileResponse(path=filepath, filename=f"balance_sheet_{as_of_date}.pdf", media_type="application/pdf")

@router.get("/general-ledger", response_model=GeneralLedger)
def get_general_ledger(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type", enum=["purchase", "sales", "expense"])
):
    return crud_financial_reports.get_general_ledger(db=db, start_date=start_date, end_date=end_date, tenant_id=tenant_id, transaction_type=transaction_type)

@router.get("/general-ledger/export")
def export_general_ledger(
    start_date: date,
    end_date: date,
    background_tasks: BackgroundTasks,
    export_format: str = Query("pdf", alias="format", description="Export format"),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    if export_format.lower() != "pdf":
        raise HTTPException(status_code=400, detail="Only PDF format is currently supported")
        
    data = crud_financial_reports.get_general_ledger(db=db, start_date=start_date, end_date=end_date, tenant_id=tenant_id, transaction_type=transaction_type)
    filepath = generate_general_ledger_pdf(data, start_date, end_date, db, tenant_id)
    background_tasks.add_task(os.remove, filepath)
    return FileResponse(path=filepath, filename=f"general_ledger_{start_date}_{end_date}.pdf", media_type="application/pdf")

@router.get("/subsidiary-ledger/purchases/{vendor_id}", response_model=PurchaseLedger)
def get_purchase_ledger(
    vendor_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    return crud_financial_reports.get_purchase_ledger(db=db, vendor_id=vendor_id, start_date=start_date, end_date=end_date, tenant_id=tenant_id)

@router.get("/subsidiary-ledger/purchases/{vendor_id}/export")
def export_purchase_ledger(
    vendor_id: int,
    background_tasks: BackgroundTasks,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    export_format: str = Query("pdf", alias="format", description="Export format"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    if export_format.lower() != "pdf":
        raise HTTPException(status_code=400, detail="Only PDF format is currently supported")
        
    data = crud_financial_reports.get_purchase_ledger(db=db, vendor_id=vendor_id, start_date=start_date, end_date=end_date, tenant_id=tenant_id)
    filepath = generate_purchase_sales_ledger_pdf(data, start_date, end_date, db, tenant_id, is_sales=False)
    background_tasks.add_task(os.remove, filepath)
    return FileResponse(path=filepath, filename=f"purchase_ledger_{vendor_id}.pdf", media_type="application/pdf")

@router.get("/subsidiary-ledger/sales/{customer_id}", response_model=SalesLedger)
def get_sales_ledger(
    customer_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    return crud_financial_reports.get_sales_ledger(db=db, customer_id=customer_id, start_date=start_date, end_date=end_date, tenant_id=tenant_id)

@router.get("/subsidiary-ledger/sales/{customer_id}/export")
def export_sales_ledger(
    customer_id: int,
    background_tasks: BackgroundTasks,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    export_format: str = Query("pdf", alias="format", description="Export format"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    if export_format.lower() != "pdf":
        raise HTTPException(status_code=400, detail="Only PDF format is currently supported")
        
    data = crud_financial_reports.get_sales_ledger(db=db, customer_id=customer_id, start_date=start_date, end_date=end_date, tenant_id=tenant_id)
    filepath = generate_purchase_sales_ledger_pdf(data, start_date, end_date, db, tenant_id, is_sales=True)
    background_tasks.add_task(os.remove, filepath)
    return FileResponse(path=filepath, filename=f"sales_ledger_{customer_id}.pdf", media_type="application/pdf")

@router.get("/subsidiary-ledger/inventory/{item_id}", response_model=InventoryLedger)
def get_inventory_ledger(
    item_id: int,
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    return crud_financial_reports.get_inventory_ledger(db=db, item_id=item_id, start_date=start_date, end_date=end_date, tenant_id=tenant_id)

@router.get("/subsidiary-ledger/inventory/{item_id}/export")
def export_inventory_ledger(
    item_id: int,
    start_date: date,
    end_date: date,
    background_tasks: BackgroundTasks,
    export_format: str = Query("pdf", alias="format", description="Export format"),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    if export_format.lower() != "pdf":
        raise HTTPException(status_code=400, detail="Only PDF format is currently supported")
        
    data = crud_financial_reports.get_inventory_ledger(db=db, item_id=item_id, start_date=start_date, end_date=end_date, tenant_id=tenant_id)
    filepath = generate_inventory_ledger_pdf(data, start_date, end_date, db, tenant_id)
    background_tasks.add_task(os.remove, filepath)
    return FileResponse(path=filepath, filename=f"inventory_ledger_{item_id}.pdf", media_type="application/pdf")
