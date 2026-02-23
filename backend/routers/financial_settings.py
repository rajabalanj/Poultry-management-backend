from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from schemas.financial_settings import FinancialSettings, FinancialSettingsUpdate
from crud import financial_settings as crud_settings
from utils.tenancy import get_tenant_id
from utils.auth_utils import require_group, get_user_identifier

router = APIRouter(
    prefix="/financial-settings",
    tags=["Financial Settings"],
)

@router.get("/", response_model=FinancialSettings)
def get_settings(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    return crud_settings.get_financial_settings(db, tenant_id)

@router.patch("/", response_model=FinancialSettings)
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