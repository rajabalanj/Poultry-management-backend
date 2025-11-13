from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from .composition_usage_item import CompositionUsageItem


class CompositionUsageHistoryBase(BaseModel):
    composition_id: int
    times: int
    used_at: datetime
    batch_id: Optional[int] = None
    tenant_id: Optional[str] = None


class CompositionUsageHistoryCreate(CompositionUsageHistoryBase):
    pass


class CompositionUsageHistory(CompositionUsageHistoryBase):
    id: int
    composition_name: Optional[str] = None
    items: List[CompositionUsageItem] = []
    shed_id: Optional[int] = None

    class Config:
        from_attributes = True
