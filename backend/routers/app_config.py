from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from database import get_db
from schemas.app_config import AppConfigCreate, AppConfigUpdate, AppConfigOut, FinancialConfig
from crud import app_config as crud_app_config
from crud import egg_room_reports as crud_egg_room_reports
from models.app_config import AppConfig as AppConfigModel
from utils.auth_utils import get_current_user, get_user_identifier, require_group
from utils.tenancy import get_tenant_id

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/configurations", response_model=AppConfigOut)
def create_config(config: AppConfigCreate, db: Session = Depends(get_db), user: dict = Depends(require_group(["admin"])), tenant_id: str = Depends(get_tenant_id)):
    return crud_app_config.create_config(db, config, tenant_id, user_id=get_user_identifier(user))


@router.get("/configurations", response_model=List[AppConfigOut])
def get_configs(name: Optional[str] = None, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    configs = crud_app_config.get_config(db, tenant_id, name=name)
    # Always return a list, even if empty
    return [configs] if name and configs else configs or []

@router.get("/configurations/financial", response_model=FinancialConfig)
def get_financial_config_endpoint(db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    return crud_app_config.get_financial_config(db, tenant_id)

@router.patch("/configurations/financial", response_model=FinancialConfig)
def update_financial_config_endpoint(config: FinancialConfig, db: Session = Depends(get_db), user: dict = Depends(require_group(["admin"])), tenant_id: str = Depends(get_tenant_id)):
    user_id = get_user_identifier(user)
    updated_configs = crud_app_config.update_financial_config(db, config.model_dump(), tenant_id, user_id)
    return updated_configs

# Standard performance source selection endpoint
@router.get("/configurations/standard-performance", response_model=AppConfigOut)
def get_standard_performance_config(db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id), user: dict = Depends(get_current_user)):
    config = crud_app_config.get_config(db, tenant_id, name="performance_standard_source")
    if not config:
        # If not set, create it with the default 'bovans' to ensure it always returns a value.
        # This makes the GET idempotent from a client's perspective: it always gets a config.
        user_id = get_user_identifier(user)
        new_config_data = AppConfigCreate(name="performance_standard_source", value="bovans")
        config = crud_app_config.create_config(db, new_config_data, tenant_id, user_id=user_id)
        logger.info(f"Created default 'performance_standard_source' for tenant {tenant_id}")
    return config

@router.patch("/configurations/standard-performance", response_model=AppConfigOut)
def update_standard_performance_config(config: AppConfigUpdate, db: Session = Depends(get_db), user: dict = Depends(require_group(["admin"])), tenant_id: str = Depends(get_tenant_id)):
    user_id = get_user_identifier(user)
    if not config.value or config.value not in ["bovans", "bv300"]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="performance_standard_source must be 'bovans' or 'bv300'")

    existing_config = crud_app_config.get_config(db, tenant_id, name="performance_standard_source")
    if existing_config:
        return crud_app_config.update_config_by_name(db, "performance_standard_source", config, tenant_id, user_id)

    from schemas.app_config import AppConfigCreate
    create_obj = AppConfigCreate(name="performance_standard_source", value=config.value)
    return crud_app_config.create_config(db, create_obj, tenant_id, user_id)

@router.get("/configurations/{name}", response_model=AppConfigOut)
def get_config_by_name(name: str, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    config = crud_app_config.get_config(db, tenant_id, name=name)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return config

@router.patch("/configurations/{name}", response_model=AppConfigOut)
def update_config(name: str, config: AppConfigUpdate, db: Session = Depends(get_db), user: dict = Depends(require_group(["admin"])), tenant_id: str = Depends(get_tenant_id)):
    user_id = get_user_identifier(user)
    
    # First, try to get the existing configuration
    existing_config = crud_app_config.get_config(db, tenant_id, name=name)
    
    if existing_config:
        # If it exists, update it
        updated = crud_app_config.update_config_by_name(db, name, config, tenant_id, user_id)
        if not updated:
            raise HTTPException(status_code=404, detail="Configuration not found during update")
        
        if name in ['table_opening', 'jumbo_opening', 'grade_c_opening']:
            crud_egg_room_reports.recalculate_inventory_from_start(db, tenant_id, user_id)
            
        return updated
    else:
        # If it does not exist, create it
        new_config_data = config.model_dump()
        new_config_data['name'] = name
        
        if 'value' not in new_config_data or new_config_data['value'] is None:
            raise HTTPException(status_code=422, detail="Field 'value' is required for creating a new configuration.")
            
        new_config = AppConfigCreate(**new_config_data)
        created = crud_app_config.create_config(db, new_config, tenant_id, user_id)
        
        if name in ['table_opening', 'jumbo_opening', 'grade_c_opening']:
            crud_egg_room_reports.recalculate_inventory_from_start(db, tenant_id, user_id)
            
        return created
