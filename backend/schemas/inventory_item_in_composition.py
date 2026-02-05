from pydantic import BaseModel
from typing import Optional, Union
from decimal import Decimal

class InventoryItemInCompositionBase(BaseModel):
    inventory_item_id: int
    weight: Decimal
    wastage_percentage: Optional[Decimal] = None
    tenant_id: Optional[str] = None


class InventoryItemInCompositionCreate(InventoryItemInCompositionBase):
    pass

class InventoryItemInComposition(InventoryItemInCompositionBase):
    id: int
    composition_id: int

    class Config:
        from_attributes = True
