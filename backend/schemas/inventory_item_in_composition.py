from pydantic import BaseModel
from typing import Optional

class InventoryItemInCompositionBase(BaseModel):
    inventory_item_id: int
    weight: float
    tenant_id: Optional[str] = None


class InventoryItemInCompositionCreate(InventoryItemInCompositionBase):
    pass

class InventoryItemInComposition(InventoryItemInCompositionBase):
    id: int
    composition_id: int

    class Config:
        from_attributes = True
