from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

# Schema for an item within a usage history record
class CompositionUsageItem(BaseModel):
    item_name: str
    item_category: str
    weight: Decimal
    wastage_percentage: Optional[Decimal] = None

    class Config:
        from_attributes = True

# Main schema for a usage history record
class CompositionUsageHistory(BaseModel):
    id: int
    composition_id: int
    composition_name: str
    batch_id: int
    times: Decimal
    used_at: datetime
    wastage_percentage: Optional[Decimal] = None
    feed_variance_weight: Optional[Decimal] = None
    items: List[CompositionUsageItem]

    class Config:
        from_attributes = True

# Schema for the feed breakdown in the by-date response
class FeedBreakdown(BaseModel):
    feed_type: str
    amount: Decimal

# Schema for the by-date response
class CompositionUsageByDate(BaseModel):
    total_feed: Decimal
    feed_breakdown: List[FeedBreakdown]

class CompositionUsageCreate(BaseModel):
    compositionId: int
    batch_no: str
    times: Decimal
    usedAt: Optional[datetime] = None
    wastage_percentage: Optional[Decimal] = None


class PaginatedCompositionUsageHistoryResponse(BaseModel):
    data: List[CompositionUsageHistory]
    total: int