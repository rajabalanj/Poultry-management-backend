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
    is_active: Optional[bool] = True  # Indicates if the batch is currently active


    @validator('opening_count')
    def validate_opening_count(cls, v):
        if v < 0:
            raise ValueError('Opening count must be greater than or equal to 0')
        return v

class BatchCreate(BatchBase):
    pass

class Batch(BatchBase):
    id: int

    class Config:
        from_attributes = True 