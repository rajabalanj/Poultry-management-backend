from pydantic import BaseModel
from typing import Optional

class AppConfigBase(BaseModel):
    name: str
    value: str
    tenant_id: Optional[str] = None

class AppConfigCreate(AppConfigBase):
    pass

class AppConfigUpdate(BaseModel):
    value: Optional[str] = None

class AppConfigOut(AppConfigBase):
    id: int

    class Config:
        from_attributes = True