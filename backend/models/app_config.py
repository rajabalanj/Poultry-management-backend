from sqlalchemy import Column, Integer, String, UniqueConstraint
from database import Base

class AppConfig(Base):
    __tablename__ = "app_config"
    __table_args__ = (UniqueConstraint('name', 'tenant_id', name='_name_tenant_uc'),)

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    value = Column(String(255), nullable=False)
    tenant_id = Column(String, index=True)