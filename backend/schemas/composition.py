from pydantic import BaseModel
from typing import List, Optional
from .inventory_item_in_composition import InventoryItemInComposition, InventoryItemInCompositionCreate

class CompositionBase(BaseModel):
    name: str
    tenant_id: Optional[str] = None


class CompositionCreate(CompositionBase):
    inventory_items: List[InventoryItemInCompositionCreate]

class Composition(CompositionBase):
    id: int
    inventory_items: List[InventoryItemInComposition]
    class Config:
        from_attributes = True
