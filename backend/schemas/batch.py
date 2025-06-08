from pydantic import BaseModel, validator, computed_field
from datetime import date
import re

class BatchBase(BaseModel):
    age: str
    opening_count: int
    mortality: int = 0
    culls: int = 0
    table_eggs: int = 0
    jumbo: int = 0
    cr: int = 0

    @validator('age')
    def validate_age_format(cls, v):
        # Check if the age matches the format week.day
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

class BatchCreate(BatchBase):
    shed_no: str

class Batch(BatchBase):
    id: int
    shed_no: str
    batch_no: str
    date: date
    closing_count: int

    @computed_field
    def calculated_closing_count(self) -> int:
        return self.opening_count - (self.mortality + self.culls)

    @computed_field
    def total_eggs(self) -> int:
        return self.table_eggs + self.jumbo + self.cr
    
    @computed_field
    def hd(self) -> int:
        return self.total_eggs / self.closing_count if self.closing_count > 0 else 0

    class Config:
        from_attributes = True 