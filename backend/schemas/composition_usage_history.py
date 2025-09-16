from typing import Optional
from pydantic import BaseModel
from datetime import datetime

class CompositionUsageHistoryBase(BaseModel):
    composition_id: int
    times: int
    used_at: datetime
    batch_id: Optional[int] = None # New field to track the batch associated with the usage
    tenant_id: str
    # shed_no: str = None  # Optional field to track the shed number

class CompositionUsageHistoryCreate(CompositionUsageHistoryBase):
    pass

class CompositionUsageHistory(CompositionUsageHistoryBase):
    id: int
    composition_name: Optional[str] = None # Add this line
    shed_no: Optional[str] = None        # Add this line
    class Config:
        from_attributes = True
