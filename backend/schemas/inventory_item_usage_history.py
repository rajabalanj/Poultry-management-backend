from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

class InventoryItemUsageHistoryCreate(BaseModel):
    inventory_item_id: int
    batch_no: str
    used_quantity: Decimal
    usedAt: Optional[datetime] = None
    unit: str

class InventoryItemUsageHistory(BaseModel):
    id: int
    inventory_item_id: int
    used_quantity: Decimal
    unit: str
    used_at: datetime
    batch_id: int
    changed_by: Optional[str] = None
    tenant_id: Optional[str] = None

    class Config:
        from_attributes = True

class PaginatedInventoryItemUsageHistoryResponse(BaseModel):
    data: List[InventoryItemUsageHistory]
    total: int

class InventoryItemUsageBreakdown(BaseModel):
    inventory_item_id: int
    name: str
    amount: Decimal
    unit: str

class InventoryItemUsageByDate(BaseModel):
    total_used: Decimal
    breakdown: List[InventoryItemUsageBreakdown]
