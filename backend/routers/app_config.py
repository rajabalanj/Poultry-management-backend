from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from database import get_db
from schemas.app_config import AppConfigCreate, AppConfigUpdate, AppConfigOut
from crud import app_config as crud_app_config
from models.app_config import AppConfig as AppConfigModel
from utils.auth_utils import get_current_user, get_user_identifier, require_group
from utils.tenancy import get_tenant_id

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/configurations/", response_model=AppConfigOut)
def create_config(config: AppConfigCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user), tenant_id: str = Depends(get_tenant_id)):
    return crud_app_config.create_config(db, config, tenant_id, user_id=get_user_identifier(user))


@router.get("/configurations/", response_model=List[AppConfigOut])
def get_configs(name: Optional[str] = None, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    configs = crud_app_config.get_config(db, tenant_id, name=name)
    # Always return a list, even if empty
    return [configs] if name and configs else configs or []

@router.patch("/configurations/{name}/", response_model=AppConfigOut)
def update_config(name: str, config: AppConfigUpdate, db: Session = Depends(get_db), user: dict = Depends(get_current_user), tenant_id: str = Depends(get_tenant_id)):
    updated = crud_app_config.update_config_by_name(db, name, config, tenant_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return updated


DEFAULT_CONFIGS = [
    {"name": "system_start_date", "value": "2024-01-01"},
    {"name": "EGG_STOCK_TOLERANCE", "value": "100"},
    {"name": "table_opening", "value": "0"},
    {"name": "jumbo_opening", "value": "0"},
    {"name": "grade_c_opening", "value": "0"},
    {"name": "lowKgThreshold", "value": "4000"},
    {"name": "lowTonThreshold", "value": "4"},
    {"name": "medicineLowKgThreshold", "value": "10"},
    {"name": "medicineLowGramThreshold", "value": "10000"},
    {"name": "henDayDeviation", "value": "10"},
]

@router.get("/tenants/configs-initialized", tags=["Tenants"])
def are_tenant_configurations_initialized(
    tenant_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_group(["admin"]))
):
    """
    Checks if the default application configurations are initialized for a tenant.
    """
    default_config_names = {config["name"] for config in DEFAULT_CONFIGS}

    existing_configs_query = db.query(AppConfigModel.name).filter(
        AppConfigModel.tenant_id == tenant_id,
        AppConfigModel.name.in_(default_config_names)
    )
    existing_config_names = {name for (name,) in existing_configs_query}

    all_configs_exist = default_config_names.issubset(existing_config_names)

    return {"configs_initialized": all_configs_exist}


@router.post("/tenants/initialize-configs", status_code=status.HTTP_201_CREATED, tags=["Tenants"])
def initialize_tenant_configurations(
    tenant_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_group(["admin"]))
):
    """
    Initializes a new tenant with a default set of application configurations.
    This is idempotent; it will not overwrite existing configurations for the tenant.
    """
    # Check which configs already exist for this tenant
    existing_configs_query = db.query(AppConfigModel.name).filter(AppConfigModel.tenant_id == tenant_id)
    existing_config_names = {name for (name,) in existing_configs_query}

    new_configs_created = []
    for config_data in DEFAULT_CONFIGS:
        if config_data["name"] not in existing_config_names:
            config = AppConfigCreate(**config_data)
            crud_app_config.create_config(db, config, tenant_id, user_id=get_user_identifier(user))
            new_configs_created.append(config_data["name"])

    if not new_configs_created:
        return {"message": f"All default configurations already exist for tenant '{tenant_id}'."}

    logger.info(f"Initialized default configs for tenant '{tenant_id}' by user {get_user_identifier(user)}. New configs: {new_configs_created}")
    return {"message": f"Successfully initialized default configurations for tenant '{tenant_id}'.", "new_configs": new_configs_created}
