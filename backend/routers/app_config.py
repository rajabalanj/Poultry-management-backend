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

@router.post("/configurations/", response_model=AppConfigOut)
def create_config(config: AppConfigCreate, db: Session = Depends(get_db), user: dict = Depends(require_group(["admin"])), tenant_id: str = Depends(get_tenant_id)):
    return crud_app_config.create_config(db, config, tenant_id, user_id=get_user_identifier(user))


@router.get("/configurations/", response_model=List[AppConfigOut])
def get_configs(name: Optional[str] = None, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    configs = crud_app_config.get_config(db, tenant_id, name=name)
    # Always return a list, even if empty
    return [configs] if name and configs else configs or []

@router.patch("/configurations/{name}/", response_model=AppConfigOut)
def update_config(name: str, config: AppConfigUpdate, db: Session = Depends(get_db), user: dict = Depends(require_group(["admin"])), tenant_id: str = Depends(get_tenant_id)):
    user_id = get_user_identifier(user)
    
    # First, try to get the existing configuration
    existing_config = crud_app_config.get_config(db, tenant_id, name=name)
    
    if existing_config:
        # If it exists, update it
        updated = crud_app_config.update_config_by_name(db, name, config, tenant_id, user_id)
        if not updated:
            # This case should ideally not be reached if existing_config was found
            raise HTTPException(status_code=404, detail="Configuration not found during update")
        
        if name in ['table_opening', 'jumbo_opening', 'grade_c_opening']:
            crud_egg_room_reports.recalculate_inventory_from_start(db, tenant_id, user_id)
            
        return updated
    else:
        # If it does not exist, create it
        # We need to construct an AppConfigCreate object from the provided AppConfigUpdate
        # and the name from the path.
        new_config_data = config.model_dump()
        new_config_data['name'] = name
        
        # Ensure 'value' is present, as it's required by AppConfigCreate
        if 'value' not in new_config_data or new_config_data['value'] is None:
            raise HTTPException(status_code=422, detail="Field 'value' is required for creating a new configuration.")
            
        new_config = AppConfigCreate(**new_config_data)
        created = crud_app_config.create_config(db, new_config, tenant_id, user_id)
        
        if name in ['table_opening', 'jumbo_opening', 'grade_c_opening']:
            crud_egg_room_reports.recalculate_inventory_from_start(db, tenant_id, user_id)
            
        return created

@router.get("/configurations/financial", response_model=FinancialConfig)
def get_financial_config_endpoint(db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    return crud_app_config.get_financial_config(db, tenant_id)

@router.patch("/configurations/financial", response_model=FinancialConfig)
def update_financial_config_endpoint(config: FinancialConfig, db: Session = Depends(get_db), user: dict = Depends(require_group(["admin"])), tenant_id: str = Depends(get_tenant_id)):
    user_id = get_user_identifier(user)
    updated_configs = crud_app_config.update_financial_config(db, config.model_dump(), tenant_id, user_id)
    return updated_configs
