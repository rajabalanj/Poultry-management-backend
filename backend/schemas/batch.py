from typing import Optional
from pydantic import BaseModel, validator, computed_field
from datetime import date
import re

class BatchBase(BaseModel):
    age: str
    opening_count: int
    batch_no: str
    shed_no: str
    date: date



    @validator('opening_count')
    def validate_opening_count(cls, v):
        if v < 0:
            raise ValueError('Opening count must be greater than or equal to 0')
        return v

class BatchCreate(BatchBase):
    pass

class Batch(BatchBase):
    id: int
    tenant_id: Optional[str] = None
    batch_type: Optional[str] = None

    class Config:
        from_attributes = True 