from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ShedBase(BaseModel):
    shed_no: str

class ShedCreate(ShedBase):
    pass

class ShedUpdate(ShedBase):
    pass

class Shed(ShedBase):
    id: int
    tenant_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
