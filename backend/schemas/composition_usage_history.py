from pydantic import BaseModel
from datetime import datetime

class CompositionUsageHistoryBase(BaseModel):
    composition_id: int
    times: int
    used_at: datetime

class CompositionUsageHistoryCreate(CompositionUsageHistoryBase):
    pass

class CompositionUsageHistory(CompositionUsageHistoryBase):
    id: int
    class Config:
        from_attributes = True
