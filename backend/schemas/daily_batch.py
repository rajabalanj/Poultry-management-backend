from pydantic import BaseModel, validator, computed_field
from datetime import date
from typing import Optional
import re

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
    is_chick_batch: bool = False

    

    @validator('age')
    def validate_age_format(cls, v):
        if not re.match(r'^\d+\.\d+$', v):
            raise ValueError('Age must be in the format week.day (e.g., "1.1")')
        week, day = map(int, v.split('.'))
        if day < 1 or day > 7:
            raise ValueError('Day must be between 1 and 7')
        if week < 1:
            raise ValueError('Week must be greater than 0')
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

class DailyBatchCreate(DailyBatchBase):
    # This class is fine as is if it serves as a distinct type for creation.
    # If it's always identical to DailyBatchBase, you might reconsider its necessity.
    pass



    @computed_field
    def closing_count(self) -> int: # Renamed from calculated_closing_count
        return self.opening_count - (self.mortality + self.culls)

    @computed_field
    def total_eggs(self) -> int:
        return self.table_eggs + self.jumbo + self.cr

    @computed_field
    def hd(self) -> float: # Renamed from calculated_HD
        closing = self.closing_count # Use the computed closing_count here
        return self.total_eggs / closing if closing > 0 else 0

    class Config:
        from_attributes = True