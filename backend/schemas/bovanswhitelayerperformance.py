from typing import List, Optional
from pydantic import BaseModel
class BovansPerformanceSchema(BaseModel):
    age_weeks: int
    livability_percent: float
    lay_percent: float
    eggs_per_bird_cum: float
    feed_intake_per_day_g: int
    feed_intake_cum_kg: float
    body_weight_g: int
    tenant_id: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    class Config:
        # This enables ORM mode, allowing Pydantic to read data directly from SQLAlchemy models.
        # It handles conversion from ORM objects to Pydantic models.
        from_attributes = True

class PaginatedBovansPerformanceResponse(BaseModel):
    data: List[BovansPerformanceSchema]
    total_count: int

    class Config:
        # This enables ORM mode, allowing Pydantic to read data directly from SQLAlchemy models.
        # It handles conversion from ORM objects to Pydantic models.
        from_attributes = True # Changed from orm_mode = True for Pydantic v2+
