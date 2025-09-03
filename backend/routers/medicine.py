from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from database import get_db
import crud.medicine as crud_medicine
import logging
from typing import List, Optional
from models.medicine import Medicine as MedicineModel
from schemas.medicine import Medicine as MedicineSchema
from models.medicine_audit import MedicineAudit as MedicineAuditModel
from utils.auth_utils import get_current_user

router = APIRouter(prefix="/medicine", tags=["medicine"])
logger = logging.getLogger("medicine")

@router.get("/{medicine_id}")
def get_medicine(medicine_id: int, db: Session = Depends(get_db)):
    """Get a specific medicine by ID."""
    db_medicine = crud_medicine.get_medicine(db, medicine_id=medicine_id)
    if db_medicine is None:
        raise HTTPException(status_code=404, detail="Medicine not found")
    return db_medicine

@router.get("/all/")
def get_all_medicines(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all medicines with pagination."""
    medicines = crud_medicine.get_all_medicines(db, skip=skip, limit=limit)
    return medicines

@router.post("/")
def create_medicine(
    medicine: MedicineSchema,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user), 
):
    """Create a new medicine."""
    return crud_medicine.create_medicine(db=db, medicine=medicine, changed_by=user.get('sub'))

@router.patch("/{medicine_id}")
def update_medicine(
    medicine_id: int,
    medicine_data: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """Update an existing medicine."""
    db_medicine = db.query(MedicineModel).filter(MedicineModel.id == medicine_id).first()
    if not db_medicine:
        return None

    old_quantity = db_medicine.quantity
    old_unit = db_medicine.unit

    # Get the new quantity and unit from the incoming data, default to old values if not provided
    new_quantity = medicine_data.get("quantity", old_quantity)
    new_unit = medicine_data.get("unit", old_unit)

    # Convert old_quantity to grams for consistent calculation
    old_quantity_grams = Decimal(str(old_quantity))
    if old_unit == 'kg':
        old_quantity_grams *= 1000
    elif old_unit == 'ton': # Assuming 'ton' might be an old unit, convert to kg first then to gram
        old_quantity_grams *= 1000000 # 1 ton = 1000 kg = 1,000,000 grams

    # Convert new_quantity to grams for consistent calculation and storage
    new_quantity_decimal = Decimal(str(new_quantity))
    if new_unit == 'kg':
        new_quantity_decimal *= 1000
    elif new_unit == 'ton': # Assuming 'ton' might be an old unit, convert to kg first then to gram
        new_quantity_decimal *= 1000000 # 1 ton = 1000 kg = 1,000,000 grams

    change_amount_grams = Decimal('0')

    # Update the provided fields first to get the latest values for audit
    for key, value in medicine_data.items():
        setattr(db_medicine, key, value)
    
    db.commit()
    db.refresh(db_medicine)

    # Audit only if quantity changed (comparison in grams)
    if old_quantity_grams != new_quantity_decimal:
        change_amount_grams = new_quantity_decimal - old_quantity_grams
        
        # Determine a simple note
        if change_amount_grams > 0:
            audit_note = "Medicine quantity increased."
        else:
            audit_note = "Medicine quantity decreased."

        audit = MedicineAuditModel(
            medicine_id=medicine_id,
            change_amount=change_amount_grams, # Store in grams
            old_weight=old_quantity_grams,     # Store in grams
            new_weight=new_quantity_decimal,   # Store in grams
            changed_by=user.get('sub'),
            note=audit_note, # Simple note
        )
        db.add(audit)
        db.commit()

    return db_medicine

@router.get("/{medicine_id}/audit/", response_model=List[dict])
def get_medicine_audit(medicine_id: int, db: Session = Depends(get_db)):
    audits = db.query(MedicineAuditModel).filter(MedicineAuditModel.medicine_id == medicine_id).order_by(MedicineAuditModel.timestamp.desc()).all()
    return [
        {
            "timestamp": a.timestamp,
            "change_amount": a.change_amount,
            "old_weight": a.old_weight,
            "new_weight": a.new_weight,
            "changed_by": a.changed_by,
            "note": a.note,
        }
        for a in audits
    ]

@router.delete("/{medicine_id}")
def delete_medicine(
    medicine_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """Delete a medicine by ID."""
    db_medicine = crud_medicine.get_medicine(db, medicine_id=medicine_id)
    if db_medicine is None:
        raise HTTPException(status_code=404, detail="Medicine not found")
    crud_medicine.delete_medicine(db=db, medicine_id=medicine_id)
    return {"message": "Medicine deleted successfully"}