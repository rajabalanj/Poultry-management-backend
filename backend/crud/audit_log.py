from sqlalchemy.orm import Session
from models.audit_log import AuditLog
from schemas.audit_log import AuditLogCreate

def create_audit_log(db: Session, log_entry: AuditLogCreate):
    db_log_entry = AuditLog(**log_entry.model_dump())
    db.add(db_log_entry)
    db.commit()
    db.refresh(db_log_entry)
    return db_log_entry
