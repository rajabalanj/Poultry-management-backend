from sqlalchemy import Column, Integer, String, Boolean, Date, Numeric
from sqlalchemy.orm import relationship
from database import Base
from models.audit_mixin import TimestampMixin

class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, unique=True, nullable=False, index=True)
    is_paid = Column(Boolean, default=False, nullable=False)
    payment_date = Column(Date, nullable=True)
    notes = Column(String, nullable=True)
