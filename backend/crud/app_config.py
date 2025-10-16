from sqlalchemy.orm import Session
from models.app_config import AppConfig
from schemas.app_config import AppConfigCreate, AppConfigUpdate
import datetime
import pytz

# Audit imports
from crud.audit_log import create_audit_log
from schemas.audit_log import AuditLogCreate
from utils import sqlalchemy_to_dict


# Create a new config entry
def create_config(db: Session, config: AppConfigCreate, tenant_id: str, user_id: str):
    db_config = AppConfig(name=config.name, value=config.value, tenant_id=tenant_id, created_by=user_id)
    db.add(db_config)
    db.commit()
    db.refresh(db_config)

    # Audit log for creation
    try:
        new_values = sqlalchemy_to_dict(db_config)
        log_entry = AuditLogCreate(
            table_name='app_config',
            record_id=str(db_config.id),
            changed_by=user_id,
            action='CREATE',
            old_values={},
            new_values=new_values
        )
        create_audit_log(db, log_entry)
    except Exception:
        pass

    return db_config


# Get config by name (or all configs)
def get_config(db: Session, tenant_id: str, name: str = None):
    if name:
        return db.query(AppConfig).filter(AppConfig.name == name, AppConfig.tenant_id == tenant_id).first()
    return db.query(AppConfig).filter(AppConfig.tenant_id == tenant_id).all()


# Update config by id or name
def update_config(db: Session, config_id: int, config: AppConfigUpdate, tenant_id: str, user_id: str):
    db_config = db.query(AppConfig).filter(AppConfig.id == config_id, AppConfig.tenant_id == tenant_id).first()
    if not db_config:
        return None

    old_values = sqlalchemy_to_dict(db_config)
    for field, value in config.model_dump(exclude_unset=True).items():
        setattr(db_config, field, value)
    db_config.updated_at = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
    db_config.updated_by = user_id
    db.commit()
    db.refresh(db_config)

    # Audit log for update
    try:
        new_values = sqlalchemy_to_dict(db_config)
        log_entry = AuditLogCreate(
            table_name='app_config',
            record_id=str(db_config.id),
            changed_by=user_id,
            action='UPDATE',
            old_values=old_values,
            new_values=new_values
        )
        create_audit_log(db, log_entry)
    except Exception:
        pass

    return db_config



# Update config by name
def update_config_by_name(db: Session, name: str, config: AppConfigUpdate, tenant_id: str, user_id: str):
    db_config = db.query(AppConfig).filter(AppConfig.name == name, AppConfig.tenant_id == tenant_id).first()
    if not db_config:
        return None

    old_values = sqlalchemy_to_dict(db_config)
    for field, value in config.model_dump(exclude_unset=True).items():
        setattr(db_config, field, value)
    db_config.updated_at = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
    db_config.updated_by = user_id
    db.commit()
    db.refresh(db_config)

    # Audit log for update by name
    try:
        new_values = sqlalchemy_to_dict(db_config)
        log_entry = AuditLogCreate(
            table_name='app_config',
            record_id=str(db_config.id),
            changed_by=user_id,
            action='UPDATE',
            old_values=old_values,
            new_values=new_values
        )
        create_audit_log(db, log_entry)
    except Exception:
        pass

    return db_config


def get_financial_config(db: Session, tenant_id: str):
    configs = db.query(AppConfig).filter(AppConfig.tenant_id == tenant_id).all()
    config_dict = {c.name: c.value for c in configs}
    return {
        "general_ledger_opening_balance": float(config_dict.get("general_ledger_opening_balance", 0.0))
    }

def update_financial_config(db: Session, config_updates: dict, tenant_id: str, user_id: str):
    for name, value in config_updates.items():
        if value is None:
            continue

        db_config = db.query(AppConfig).filter(AppConfig.name == name, AppConfig.tenant_id == tenant_id).first()
        if db_config:
            old_values = sqlalchemy_to_dict(db_config)
            db_config.value = str(value)
            db_config.updated_at = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
            db_config.updated_by = user_id
            action = 'UPDATE'
        else:
            db_config = AppConfig(name=name, value=str(value), tenant_id=tenant_id, created_by=user_id)
            db.add(db_config)
            old_values = {}
            action = 'CREATE'
        
        db.commit()
        db.refresh(db_config)

        try:
            new_values = sqlalchemy_to_dict(db_config)
            log_entry = AuditLogCreate(
                table_name='app_config',
                record_id=str(db_config.id),
                changed_by=user_id,
                action=action,
                old_values=old_values,
                new_values=new_values
            )
            create_audit_log(db, log_entry)
        except Exception:
            pass
    
    db.commit()
    return get_financial_config(db, tenant_id)