from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional
import logging
from schemas.purchase_orders import PurchaseOrder

from database import get_db
from models.vendors import Vendor as VendorModel
from models.purchase_orders import PurchaseOrder as PurchaseOrderModel
from schemas.vendors import Vendor, VendorCreate, VendorUpdate, VendorStatus

router = APIRouter(prefix="/vendors", tags=["Vendors"])
logger = logging.getLogger("vendors")

@router.post("/", response_model=Vendor, status_code=status.HTTP_201_CREATED)
def create_vendor(
    vendor: VendorCreate,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Create a new vendor."""
    db_vendor = db.query(VendorModel).filter(VendorModel.name == vendor.name).first()
    if db_vendor:
        raise HTTPException(status_code=400, detail="Vendor with this name already exists")
    
    db_vendor = VendorModel(**vendor.model_dump())
    db.add(db_vendor)
    db.commit()
    db.refresh(db_vendor)
    logger.info(f"Vendor '{db_vendor.name}' created by {x_user_id}")
    return db_vendor

@router.get("/", response_model=List[Vendor])
def read_vendors(
    skip: int = 0,
    limit: int = 100,
    status: Optional[VendorStatus] = None, # Allow filtering by status
    db: Session = Depends(get_db)
):
    """Retrieve a list of vendors, with optional filtering by status."""
    query = db.query(VendorModel)
    if status:
        query = query.filter(VendorModel.status == status)
    vendors = query.offset(skip).limit(limit).all()
    return vendors

@router.get("/{vendor_id}", response_model=Vendor)
def read_vendor(vendor_id: int, db: Session = Depends(get_db)):
    """Retrieve a single vendor by ID."""
    db_vendor = db.query(VendorModel).filter(VendorModel.id == vendor_id).first()
    if db_vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return db_vendor

@router.patch("/{vendor_id}", response_model=Vendor)
def update_vendor(
    vendor_id: int,
    vendor: VendorUpdate,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Update an existing vendor."""
    db_vendor = db.query(VendorModel).filter(VendorModel.id == vendor_id).first()
    if db_vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    # Check if name is being updated to an existing name
    if vendor.name is not None and vendor.name != db_vendor.name:
        existing_vendor = db.query(VendorModel).filter(VendorModel.name == vendor.name).first()
        if existing_vendor:
            raise HTTPException(status_code=400, detail="Vendor with this name already exists")

    vendor_data = vendor.model_dump(exclude_unset=True)
    for key, value in vendor_data.items():
        setattr(db_vendor, key, value)
    
    db.commit()
    db.refresh(db_vendor)
    logger.info(f"Vendor '{db_vendor.name}' (ID: {vendor_id}) updated by {x_user_id}")
    return db_vendor

@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vendor(
    vendor_id: int,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Delete a vendor. Vendors with associated purchase orders cannot be hard deleted."""
    db_vendor = db.query(VendorModel).filter(VendorModel.id == vendor_id).first()
    if db_vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    # Check for associated purchase orders (soft delete recommended)
    associated_pos = db.query(PurchaseOrderModel).filter(PurchaseOrderModel.vendor_id == vendor_id).first()
    if associated_pos:
        # Instead of hard delete, set status to INACTIVE
        db_vendor.status = VendorStatus.INACTIVE
        db.commit()
        db.refresh(db_vendor)
        logger.warning(f"Vendor '{db_vendor.name}' (ID: {vendor_id}) could not be hard deleted due to associated POs. Status set to INACTIVE by {x_user_id}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Vendor '{db_vendor.name}' has associated purchase orders and cannot be hard deleted. Status changed to Inactive."
        )
    
    db.delete(db_vendor)
    db.commit()
    logger.info(f"Vendor '{db_vendor.name}' (ID: {vendor_id}) hard deleted by {x_user_id}")
    return {"message": "Vendor deleted successfully (hard delete)"}

# Endpoint for vendor's purchase history
@router.get("/{vendor_id}/purchase-history", response_model=List[PurchaseOrder])
def get_vendor_purchase_history(
    vendor_id: int,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """Retrieve purchase history for a specific vendor."""
    db_vendor = db.query(VendorModel).filter(VendorModel.id == vendor_id).first()
    if db_vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    # Eagerly load items and payments for the response model
    purchase_history = (
        db.query(PurchaseOrderModel)
        .filter(PurchaseOrderModel.vendor_id == vendor_id)
        .options(
            # Selectinload is often efficient for one-to-many relationships
            # but depends on your specific data access patterns.
            # Joinedload might be better for one-to-one or small sets.
            # We'll use selectinload for demonstration.
            selectinload(PurchaseOrderModel.items),
            selectinload(PurchaseOrderModel.payments)
        )
        .order_by(PurchaseOrderModel.order_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return purchase_history