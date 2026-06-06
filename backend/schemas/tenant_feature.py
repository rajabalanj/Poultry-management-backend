from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime

class TenantFeatureBase(BaseModel):
    tenant_id: str
    feature_name: Literal["BATCH_MANAGEMENT", "INVENTORY_USAGE"]
    is_restricted: bool = False

class TenantFeatureCreate(TenantFeatureBase):
    pass

class TenantFeatureUpdate(BaseModel):
    is_restricted: Optional[bool] = None

class TenantFeature(TenantFeatureBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True