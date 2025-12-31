from sqlalchemy import Column, Integer, String, UniqueConstraint, Boolean
from database import Base
from models.audit_mixin import TimestampMixin

class Shed(Base, TimestampMixin):
    __tablename__ = "sheds"
    __table_args__ = (UniqueConstraint('shed_no', 'tenant_id', name='_shed_no_tenant_uc'),)

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True, nullable=False)
    shed_no = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
