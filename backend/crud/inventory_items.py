from datetime import datetime
import pytz
from sqlalchemy.orm import Session
from models.inventory_items import InventoryItem
from schemas.inventory_items import InventoryItemCreate, InventoryItemUpdate
from utils.auth_utils import get_user_identifier
from crud.audit_log import create_audit_log
from schemas.audit_log import AuditLogCreate
from utils import sqlalchemy_to_dict

def get_inventory_item(db: Session, item_id: int, tenant_id: str):
    return db.query(InventoryItem).filter(InventoryItem.id == item_id, InventoryItem.tenant_id == tenant_id).first()

def get_inventory_items(db: Session, tenant_id: str, skip: int = 0, limit: int = 100):
    return db.query(InventoryItem).filter(InventoryItem.tenant_id == tenant_id).offset(skip).limit(limit).all()

def create_inventory_item(db: Session, item: InventoryItemCreate, tenant_id: str, user: dict):
    user_identifier = get_user_identifier(user)
    db_item = InventoryItem(**item.model_dump(), tenant_id=tenant_id, created_by=user_identifier, updated_by=user_identifier)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

def update_inventory_item(db: Session, item_id: int, item: InventoryItemUpdate, tenant_id: str, user: dict):
    db_item = db.query(InventoryItem).filter(InventoryItem.id == item_id, InventoryItem.tenant_id == tenant_id).first()
    if db_item:
        old_values = sqlalchemy_to_dict(db_item)
        update_data = item.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_item, key, value)
        db_item.updated_by = get_user_identifier(user)
        db.commit()
        db.refresh(db_item)
        new_values = sqlalchemy_to_dict(db_item)
        log_entry = AuditLogCreate(
            table_name='inventory_items',
            record_id=str(item_id),
            changed_by=get_user_identifier(user),
            action='UPDATE',
            old_values=old_values,
            new_values=new_values
        )
        create_audit_log(db=db, log_entry=log_entry)
    return db_item

def delete_inventory_item(db: Session, item_id: int, tenant_id: str, user: dict):
    db_item = db.query(InventoryItem).filter(InventoryItem.id == item_id, InventoryItem.tenant_id == tenant_id).first()
    if db_item:
        old_values = sqlalchemy_to_dict(db_item)
        try:
            db.delete(db_item)
            db.commit()
        except Exception:
            db.rollback()
            return False

        try:
            log_entry = AuditLogCreate(
                table_name='inventory_items',
                record_id=str(item_id),
                changed_by=get_user_identifier(user),
                action='DELETE',
                old_values=old_values,
                new_values=None
            )
            create_audit_log(db=db, log_entry=log_entry)
        except Exception:
            pass
        return True
    return False
