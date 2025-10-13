from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from database import get_db
from models.inventory_items import InventoryItem as InventoryItemModel
from schemas.inventory_items import InventoryItem, InventoryItemCreate, InventoryItemUpdate
from schemas.inventory_item_audit import InventoryItemAudit
from utils.auth_utils import get_current_user, get_user_identifier
from crud import inventory_items as crud_inventory_items
from crud import inventory_item_audit as crud_inventory_item_audit
from utils.tenancy import get_tenant_id

router = APIRouter(prefix="/inventory-items", tags=["Inventory Items"])
logger = logging.getLogger("inventory_items")

@router.post("/", response_model=InventoryItem, status_code=status.HTTP_201_CREATED)
def create_inventory_item(
    item: InventoryItemCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Create a new inventory item."""
    db_item = db.query(InventoryItemModel).filter(InventoryItemModel.name == item.name, InventoryItemModel.tenant_id == tenant_id).first()
    if db_item:
        raise HTTPException(status_code=400, detail="Inventory item with this name already exists")
    
    new_item = crud_inventory_items.create_inventory_item(db=db, item=item, tenant_id=tenant_id, user=user)
    logger.info(f"Inventory item '{new_item.name}' created by user {get_user_identifier(user)} for tenant {tenant_id}")
    return new_item

@router.get("/", response_model=List[InventoryItem])
def read_inventory_items(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None, # Allow filtering by category
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    """Retrieve a list of inventory items, with optional filtering by category."""
    # The filtering logic will remain here, as it's a query parameter concern
    query = db.query(InventoryItemModel).filter(InventoryItemModel.tenant_id == tenant_id)
    if category:
        query = query.filter(InventoryItemModel.category == category)
    items = query.offset(skip).limit(limit).all()
    return items

@router.get("/{item_id}", response_model=InventoryItem)
def read_inventory_item(item_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    """Retrieve a single inventory item by ID."""
    db_item = crud_inventory_items.get_inventory_item(db=db, item_id=item_id, tenant_id=tenant_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return db_item

@router.patch("/{item_id}", response_model=InventoryItem)
def update_inventory_item(
    item_id: int,
    item: InventoryItemUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Update an existing inventory item."""
    db_item = crud_inventory_items.get_inventory_item(db=db, item_id=item_id, tenant_id=tenant_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    # Check if name is being updated to an existing name
    if item.name is not None and item.name != db_item.name:
        existing_item = db.query(InventoryItemModel).filter(InventoryItemModel.name == item.name, InventoryItemModel.tenant_id == tenant_id).first()
        if existing_item:
            raise HTTPException(status_code=400, detail="Inventory item with this name already exists")

    updated_item = crud_inventory_items.update_inventory_item(db=db, item_id=item_id, item=item, tenant_id=tenant_id, user=user)
    logger.info(f"Inventory item '{updated_item.name}' (ID: {item_id}) updated by user {get_user_identifier(user)} for tenant {tenant_id}")
    return updated_item

@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inventory_item(
    item_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Delete an inventory item. Items with associated purchase order items cannot be deleted."""
    db_item = crud_inventory_items.get_inventory_item(db=db, item_id=item_id, tenant_id=tenant_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    # Check for associated purchase order items
    from models.purchase_order_items import PurchaseOrderItem as PurchaseOrderItemModel
    associated_po_items = db.query(PurchaseOrderItemModel).filter(PurchaseOrderItemModel.inventory_item_id == item_id).first()
    if associated_po_items:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Inventory item has associated purchase order items and cannot be deleted."
        )
    
    crud_inventory_items.delete_inventory_item(db=db, item_id=item_id, tenant_id=tenant_id, user=user)
    logger.info(f"Inventory item '{db_item.name}' (ID: {item_id}) deleted by user {get_user_identifier(user)} for tenant {tenant_id}")
    return {"message": "Inventory item deleted successfully"}

@router.get("/{item_id}/audit", response_model=List[InventoryItemAudit])
def get_inventory_item_audit_history(item_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    """
    Retrieve the audit history for a specific inventory item.
    """
    db_item = crud_inventory_items.get_inventory_item(db=db, item_id=item_id, tenant_id=tenant_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    audit_history = crud_inventory_item_audit.get_inventory_item_audits(db=db, inventory_item_id=item_id, tenant_id=tenant_id)
    return audit_history
