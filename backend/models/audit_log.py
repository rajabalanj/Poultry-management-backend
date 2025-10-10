from sqlalchemy import Column, Integer, String, DateTime, JSON, func
from database import Base
from datetime import datetime
import pytz

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    table_name = Column(String, nullable=False)
    record_id = Column(Integer, nullable=False)
    changed_at = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Kolkata')))
    changed_by = Column(String, nullable=False)
    action = Column(String, nullable=False)  # e.g., 'INSERT', 'UPDATE', 'DELETE'
    old_values = Column(JSON)
    new_values = Column(JSON)
