from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime

class InventoryItemBase(BaseModel):
    name: str
    unit: str # e.g., "kg", "tons", "liters", "units"
    category: Optional[str] = None
    # current_stock and average_cost typically not set on create, managed by system
    reorder_level: Optional[Decimal] = None
    description: Optional[str] = None

class InventoryItemCreate(InventoryItemBase):
    pass

class InventoryItemUpdate(BaseModel):
    name: Optional[str] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    # current_stock and average_cost are system-managed, not directly updated via this schema
    reorder_level: Optional[Decimal] = None
    description: Optional[str] = None

class InventoryItem(InventoryItemBase):
    id: int
    tenant_id: Optional[str] = None
    current_stock: Decimal # Included in response to show current stock
    average_cost: Decimal # Included in response
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
