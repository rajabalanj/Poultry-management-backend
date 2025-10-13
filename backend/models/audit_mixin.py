from sqlalchemy import Column, DateTime, String
from datetime import datetime
import pytz

class AuditMixin:
    # Use timezone-aware timestamps to ensure all dates are stored in the desired timezone (Asia/Kolkata).
    # DateTime(timezone=True) ensures the timezone info is persisted in the database.
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.timezone('Asia/Kolkata')))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(pytz.timezone('Asia/Kolkata')))
    created_by = Column(String, nullable=True)
    updated_by = Column(String, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(String, nullable=True)
