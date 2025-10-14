from sqlalchemy import Column, Integer, String, UniqueConstraint
from database import Base
from models.audit_mixin import TimestampMixin

class AppConfig(Base, TimestampMixin):
    __tablename__ = "app_config"
    __table_args__ = (UniqueConstraint('name', 'tenant_id', name='_app_config_name_tenant_uc'),)

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    value = Column(String(255), nullable=False)
    tenant_id = Column(String, index=True)