from pydantic import BaseModel
from datetime import datetime

class CompositionUsageHistoryBase(BaseModel):
    composition_id: int
    times: int
    used_at: datetime
    batch_id: int  # New field to track the batch associated with the usage

class CompositionUsageHistoryCreate(CompositionUsageHistoryBase):
    pass

class CompositionUsageHistory(CompositionUsageHistoryBase):
    id: int
    class Config:
        from_attributes = True
