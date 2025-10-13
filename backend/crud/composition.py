from sqlalchemy.orm import Session
from models.composition import Composition
from models.inventory_item_in_composition import InventoryItemInComposition
from schemas.composition import CompositionCreate

# Audit imports
from crud.audit_log import create_audit_log
from schemas.audit_log import AuditLogCreate
from utils import sqlalchemy_to_dict
import datetime
import pytz


def create_composition(db: Session, composition: CompositionCreate, tenant_id: str, user_id: str):
    db_composition = Composition(name=composition.name, tenant_id=tenant_id, created_by=user_id)
    db.add(db_composition)
    db.flush()
    for item in composition.inventory_items:
        db_item = InventoryItemInComposition(
            composition_id=db_composition.id,
            inventory_item_id=item.inventory_item_id,
            weight=item.weight,
            tenant_id=tenant_id
        )
        db.add(db_item)
    db.commit()
    db.refresh(db_composition)

    # Audit log for creation
    try:
        new_values = sqlalchemy_to_dict(db_composition)
        log_entry = AuditLogCreate(
            table_name='composition',
            record_id=db_composition.id,
            changed_by=user_id,
            action='CREATE',
            old_values={},
            new_values=new_values
        )
        create_audit_log(db, log_entry)
    except Exception:
        pass

    return db_composition


def get_composition(db: Session, composition_id: int, tenant_id: str):
    return db.query(Composition).filter(Composition.id == composition_id, Composition.tenant_id == tenant_id).first()


def get_compositions(db: Session, tenant_id: str, skip: int = 0, limit: int = 100):
    return db.query(Composition).filter(Composition.tenant_id == tenant_id).offset(skip).limit(limit).all()


def update_composition(db: Session, composition_id: int, composition: CompositionCreate, tenant_id: str, user_id: str):
    db_composition = db.query(Composition).filter(Composition.id == composition_id, Composition.tenant_id == tenant_id).first()
    if not db_composition:
        return None

    old_values = sqlalchemy_to_dict(db_composition)

    db_composition.name = composition.name
    db_composition.updated_by = user_id
    db.query(InventoryItemInComposition).filter(InventoryItemInComposition.composition_id == composition_id, InventoryItemInComposition.tenant_id == tenant_id).delete()
    for item in composition.inventory_items:
        db_item = InventoryItemInComposition(
            composition_id=composition_id,
            inventory_item_id=item.inventory_item_id,
            weight=item.weight,
            tenant_id=tenant_id
        )
        db.add(db_item)
    db.commit()
    db.refresh(db_composition)

    # Audit log for update
    try:
        new_values = sqlalchemy_to_dict(db_composition)
        log_entry = AuditLogCreate(
            table_name='composition',
            record_id=db_composition.id,
            changed_by=user_id,
            action='UPDATE',
            old_values=old_values,
            new_values=new_values
        )
        create_audit_log(db, log_entry)
    except Exception:
        pass

    return db_composition


def delete_composition(db: Session, composition_id: int, tenant_id: str, user_id: str = None):
    db_composition = db.query(Composition).filter(Composition.id == composition_id, Composition.tenant_id == tenant_id).first()
    if not db_composition:
        return False
    # Capture old values for audit
    try:
        old_values = sqlalchemy_to_dict(db_composition)
    except Exception:
        old_values = None

    # Soft-delete: set deleted_at and deleted_by
    try:
        db_composition.deleted_at = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
        db_composition.deleted_by = user_id
        db.add(db_composition)
        db.commit()
        db.refresh(db_composition)
    except Exception:
        # Fallback to hard delete if soft-delete fails (should be rare)
        try:
            db.delete(db_composition)
            db.commit()
        except Exception:
            pass

    # Audit log for deletion
    try:
        new_values = sqlalchemy_to_dict(db_composition)
        log_entry = AuditLogCreate(
            table_name='composition',
            record_id=composition_id,
            changed_by=user_id,
            action='DELETE',
            old_values=old_values or {},
            new_values=new_values or {}
        )
        create_audit_log(db, log_entry)
    except Exception:
        pass

    return True