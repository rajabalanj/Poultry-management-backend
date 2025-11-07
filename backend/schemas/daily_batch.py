from pydantic import BaseModel, validator, computed_field
from datetime import date
from typing import Optional
class DailyBatchBase(BaseModel):
    shed_no: str
    batch_no: str
    age: str
    opening_count: int
    mortality: int = 0
    culls: int = 0
    table_eggs: int = 0
    jumbo: int = 0
    cr: int = 0
    batch_date: date
    upload_date: date
    batch_id: int

    @validator('age')
    def validate_age(cls, v):
        try:
            age_float = float(v)
            if age_float < 1.1:
                raise ValueError('Age must be 1.1 or greater')
        except ValueError:
            raise ValueError('Age must be a valid number')
        return v

    @validator('opening_count')
    def validate_opening_count(cls, v):
        if v < 0:
            raise ValueError('Opening count must be greater than or equal to 0')
        return v

    @validator('mortality', 'culls', 'table_eggs', 'jumbo', 'cr')
    def validate_non_negative(cls, v):
        if v < 0:
            raise ValueError('Value must be greater than or equal to 0')
        return v

    @computed_field
    def closing_count(self) -> int:
        return self.opening_count - (self.mortality + self.culls)

    @computed_field
    def total_eggs(self) -> int:
        return self.table_eggs + self.jumbo + self.cr

    @computed_field
    def hd(self) -> float:
        closing = self.closing_count
        return self.total_eggs / closing if closing > 0 else 0

class DailyBatchCreate(DailyBatchBase):
    # This class is fine as is if it serves as a distinct type for creation.
    # If it's always identical to DailyBatchBase, you might reconsider its necessity.
    tenant_id: Optional[str] = None
    notes: Optional[str] = None
    standard_hen_day_percentage: Optional[float] = 0.0

class DailyBatchUpdate(DailyBatchBase):
    batch_id: int
    notes: Optional[str] = None
    standard_hen_day_percentage: Optional[float] = 0.0
    feed_in_kg: Optional[float] = None
    standard_feed_in_kg: Optional[float] = None
    

    class Config:
        from_attributes = True

class DailyBatch(DailyBatchBase):
    tenant_id: Optional[str] = None
    feed_in_kg: Optional[float] = None
    standard_feed_in_kg: Optional[float] = None

    class Config:
        from_attributes = True
