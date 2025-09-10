from pydantic import BaseModel

class InventoryItemInCompositionBase(BaseModel):
    inventory_item_id: int
    weight: float

class InventoryItemInCompositionCreate(InventoryItemInCompositionBase):
    pass

class InventoryItemInComposition(InventoryItemInCompositionBase):
    id: int
    composition_id: int

    class Config:
        from_attributes = True
