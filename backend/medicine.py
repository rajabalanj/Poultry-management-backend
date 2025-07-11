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
    x_user_id: Optional[str] = Header(None)
):
    """Create a new medicine."""
    return crud_medicine.create_medicine(db=db, medicine=medicine, changed_by=x_user_id)

@router.patch("/{medicine_id}")
def update_medicine(
    medicine_id: int,
    medicine_data: dict,
    db: Session = Depends(get_db),
    changed_by: str = None
):
    """Update an existing medicine."""
    db_medicine = db.query(MedicineModel).filter(MedicineModel.id == medicine_id).first()
    if not db_medicine:
        return None

    old_quantity = db_medicine.quantity
    old_unit = db_medicine.unit  # Get the old unit
    new_quantity = medicine_data.get("quantity", old_quantity)
    new_unit = medicine_data.get("unit", old_unit) # Get the new unit

    # Initialize new_quantity_decimal and change_amount
    new_quantity_decimal = Decimal(str(new_quantity)) # Convert new_quantity to Decimal
    change_amount = Decimal('0') # Initialize to Decimal 0

    # Unit conversion logic (assuming medicine_data['unit'] is the new unit)
    if old_unit == 'kg' and new_unit == 'gram':
        # Convert old quantity to grams for consistent comparison if unit changes
        old_quantity_for_comparison = old_quantity * 1000
    elif old_unit == 'gram' and new_unit == 'kg':
        # Convert old quantity to kilograms for consistent comparison if unit changes
        old_quantity_for_comparison = old_quantity / 1000
    else:
        old_quantity_for_comparison = old_quantity

    if new_quantity_decimal is not None and old_quantity_for_comparison != new_quantity_decimal:
        change_amount = new_quantity_decimal - Decimal(str(old_quantity_for_comparison)) # Calculate change based on converted old quantity

    # Update the provided fields
    for key, value in medicine_data.items():
        setattr(db_medicine, key, value)

    db.commit()
    db.refresh(db_medicine)

    # Audit only if quantity changed
    if old_quantity_for_comparison != new_quantity_decimal:
        audit_note = f"Old Weight: {old_quantity} {old_unit}, New Weight: {new_quantity_decimal} {new_unit}"
        if change_amount > 0:
            audit_note += f", Added: {change_amount} {new_unit}"
        else:
            audit_note += f", Removed: {abs(change_amount)} {new_unit}"

        audit = MedicineAuditModel(
            medicine_id=medicine_id,
            change_amount=change_amount,
            old_weight=old_quantity,
            new_weight=new_quantity_decimal,
            changed_by=changed_by,
            note=audit_note, # Include units in the note
        )
        db.add(audit)
        db.commit()

    return db_medicine
@router.get("/{medicine_id}/audit/", response_model=List[dict])
def get_feed_audit(medicine_id: int, db: Session = Depends(get_db)):
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
    x_user_id: Optional[str] = Header(None)
):
    """Delete a specific medicine."""
    success = crud_medicine.delete_medicine(db, medicine_id=medicine_id, changed_by=x_user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Medicine not found")
    return {"message": "Medicine deleted successfully"}