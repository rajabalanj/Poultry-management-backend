from typing import Optional
from pydantic import BaseModel, validator
from datetime import date

class BatchBase(BaseModel):
    age: str
    opening_count: int
    batch_no: str
    shed_id: int
    date: date

    @validator('opening_count')
    def validate_opening_count(cls, v):
        if v < 0:
            raise ValueError('Opening count must be greater than or equal to 0')
        return v

    @validator('age')
    def validate_age(cls, v):
        try:
            age_float = float(v)
            if age_float < 0.1:
                raise ValueError('Age must be 0.1 or greater')
        except ValueError:
            raise ValueError('Age must be a valid number')
        return v

class BatchCreate(BatchBase):
    pass

class Batch(BaseModel):
    id: int
    age: str
    opening_count: int
    batch_no: str
    date: date
    tenant_id: Optional[str] = None
    batch_type: Optional[str] = None

    class Config:
        from_attributes = True

class ShedInfo(BaseModel):
    id: int
    shed_no: str

class BatchResponse(Batch):
    current_shed: Optional[ShedInfo] = None
    is_active: Optional[bool] = None