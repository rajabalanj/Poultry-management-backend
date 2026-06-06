from sqlalchemy import Column, Integer, String, Boolean
from database import Base
from models.audit_mixin import TimestampMixin

class TenantFeature(Base, TimestampMixin):
    __tablename__ = "tenant_features"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True, nullable=False)
    feature_name = Column(String, index=True, nullable=False) # e.g., "BATCH_MANAGEMENT", "INVENTORY_USAGE"
    is_restricted = Column(Boolean, default=False, nullable=False)