from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from crud import inventory_item_variant as crud
from schemas.inventory_item_variant import InventoryItemVariant, InventoryItemVariantCreate
from utils.tenancy import get_tenant_id
from utils.auth_utils import get_current_user

router = APIRouter()

@router.post("/inventory-item-variants/", response_model=InventoryItemVariant, tags=["Inventory Item Variants"])
def create_inventory_item_variant(variant: InventoryItemVariantCreate, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id), user: dict = Depends(get_current_user)):
    return crud.create_inventory_item_variant(db=db, variant=variant, tenant_id=tenant_id)

@router.get("/inventory-item-variants/{item_id}", response_model=List[InventoryItemVariant], tags=["Inventory Item Variants"])
def read_inventory_item_variants(item_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id), user: dict = Depends(get_current_user)):
    return crud.get_inventory_item_variants_by_item(db=db, item_id=item_id, tenant_id=tenant_id)

@router.delete("/inventory-item-variants/{variant_id}", response_model=InventoryItemVariant, tags=["Inventory Item Variants"])
def delete_inventory_item_variant(variant_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id), user: dict = Depends(get_current_user)):
    deleted_variant = crud.delete_inventory_item_variant(db=db, variant_id=variant_id, tenant_id=tenant_id)
    if deleted_variant is None:
        raise HTTPException(status_code=404, detail="Variant not found")
    return deleted_variant
