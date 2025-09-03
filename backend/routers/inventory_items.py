from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from decimal import Decimal

from database import get_db
from models.inventory_items import InventoryItem as InventoryItemModel
from schemas.inventory_items import InventoryItem, InventoryItemCreate, InventoryItemUpdate
from utils.auth_utils import get_current_user
router = APIRouter(prefix="/inventory-items", tags=["Inventory Items"])
logger = logging.getLogger("inventory_items")

@router.post("/", response_model=InventoryItem, status_code=status.HTTP_201_CREATED)
def create_inventory_item(
    item: InventoryItemCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """Create a new inventory item."""
    db_item = db.query(InventoryItemModel).filter(InventoryItemModel.name == item.name).first()
    if db_item:
        raise HTTPException(status_code=400, detail="Inventory item with this name already exists")
    
    db_item = InventoryItemModel(**item.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    logger.info(f"Inventory item '{db_item.name}' created by user {user.get('sub')}")
    return db_item

@router.get("/", response_model=List[InventoryItem])
def read_inventory_items(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None, # Allow filtering by category
    db: Session = Depends(get_db)
):
    """Retrieve a list of inventory items, with optional filtering by category."""
    query = db.query(InventoryItemModel)
    if category:
        query = query.filter(InventoryItemModel.category == category)
    items = query.offset(skip).limit(limit).all()
    return items

@router.get("/{item_id}", response_model=InventoryItem)
def read_inventory_item(item_id: int, db: Session = Depends(get_db)):
    """Retrieve a single inventory item by ID."""
    db_item = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_id).first()
    if db_item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return db_item

@router.patch("/{item_id}", response_model=InventoryItem)
def update_inventory_item(
    item_id: int,
    item: InventoryItemUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """Update an existing inventory item."""
    db_item = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_id).first()
    if db_item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    # Check if name is being updated to an existing name
    if item.name is not None and item.name != db_item.name:
        existing_item = db.query(InventoryItemModel).filter(InventoryItemModel.name == item.name).first()
        if existing_item:
            raise HTTPException(status_code=400, detail="Inventory item with this name already exists")

    item_data = item.model_dump(exclude_unset=True)
    for key, value in item_data.items():
        setattr(db_item, key, value)
    
    db.commit()
    db.refresh(db_item)
    logger.info(f"Inventory item '{db_item.name}' (ID: {item_id}) updated by user {user.get('sub')}")
    return db_item

@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inventory_item(
    item_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """Delete an inventory item. Items with associated purchase order items cannot be deleted."""
    db_item = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_id).first()
    if db_item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    # Check for associated purchase order items
    # You might want a soft delete here too, similar to vendors
    from models.purchase_order_items import PurchaseOrderItem as PurchaseOrderItemModel # Avoid circular import if this is directly in main router file
    associated_po_items = db.query(PurchaseOrderItemModel).filter(PurchaseOrderItemModel.inventory_item_id == item_id).first()
    if associated_po_items:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Inventory item has associated purchase order items and cannot be deleted."
        )
    
    db.delete(db_item)
    db.commit()
    logger.info(f"Inventory item '{db_item.name}' (ID: {item_id}) deleted by user {user.get('sub')}")
    return {"message": "Inventory item deleted successfully"}