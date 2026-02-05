from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from decimal import Decimal

class InventoryItemAuditBase(BaseModel):
    inventory_item_id: int
    change_type: str
    change_amount: Decimal
    old_quantity: Decimal
    new_quantity: Decimal
    changed_by: Optional[str] = None
    note: Optional[str] = None
    tenant_id: Optional[str] = None

class InventoryItemAuditCreate(InventoryItemAuditBase):
    pass

class InventoryItemAudit(InventoryItemAuditBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True
