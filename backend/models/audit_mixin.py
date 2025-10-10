from sqlalchemy import Column, DateTime, String, func
from datetime import datetime
import pytz

class AuditMixin:
    created_at = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Kolkata')))
    updated_at = Column(DateTime, onupdate=lambda: datetime.now(pytz.timezone('Asia/Kolkata')))
    created_by = Column(String, nullable=True)
    updated_by = Column(String, nullable=True)
