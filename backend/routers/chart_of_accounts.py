
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from schemas.chart_of_accounts import ChartOfAccounts, ChartOfAccountsCreate, ChartOfAccountsUpdate
from models import chart_of_accounts as chart_of_accounts_model
from utils.tenancy import get_tenant_id

router = APIRouter(
    prefix="/chart-of-accounts",
    tags=["Chart of Accounts"],
)

@router.post("/", response_model=ChartOfAccounts, status_code=status.HTTP_201_CREATED)
def create_account(
    account: ChartOfAccountsCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    # Check if account code already exists for this tenant
    existing_account = db.query(chart_of_accounts_model.ChartOfAccounts).filter(
        chart_of_accounts_model.ChartOfAccounts.account_code == account.account_code,
        chart_of_accounts_model.ChartOfAccounts.tenant_id == tenant_id
    ).first()

    if existing_account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account with code {account.account_code} already exists"
        )

    account_data = account.model_dump()
    account_data['tenant_id'] = tenant_id
    db_account = chart_of_accounts_model.ChartOfAccounts(**account_data)
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    return db_account

@router.get("/", response_model=List[ChartOfAccounts])
def get_accounts(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    account_type: str = None
):
    query = db.query(chart_of_accounts_model.ChartOfAccounts).filter(
        chart_of_accounts_model.ChartOfAccounts.tenant_id == tenant_id,
        chart_of_accounts_model.ChartOfAccounts.is_active == True
    )

    if account_type:
        query = query.filter(chart_of_accounts_model.ChartOfAccounts.account_type == account_type)

    return query.all()

@router.get("/{account_id}", response_model=ChartOfAccounts)
def get_account(
    account_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    account = db.query(chart_of_accounts_model.ChartOfAccounts).filter(
        chart_of_accounts_model.ChartOfAccounts.id == account_id,
        chart_of_accounts_model.ChartOfAccounts.tenant_id == tenant_id
    ).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account with id {account_id} not found"
        )

    return account

@router.patch("/{account_id}", response_model=ChartOfAccounts)
def update_account(
    account_id: int,
    account_update: ChartOfAccountsUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    account = db.query(chart_of_accounts_model.ChartOfAccounts).filter(
        chart_of_accounts_model.ChartOfAccounts.id == account_id,
        chart_of_accounts_model.ChartOfAccounts.tenant_id == tenant_id
    ).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account with id {account_id} not found"
        )

    update_data = account_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(account, key, value)

    db.commit()
    db.refresh(account)
    return account

@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    account = db.query(chart_of_accounts_model.ChartOfAccounts).filter(
        chart_of_accounts_model.ChartOfAccounts.id == account_id,
        chart_of_accounts_model.ChartOfAccounts.tenant_id == tenant_id
    ).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account with id {account_id} not found"
        )

    # Soft delete by setting is_active to False
    account.is_active = False
    db.commit()
    return None