from sqlalchemy.orm import Session
from models.medicine_usage_history import MedicineUsageHistory
from models.medicine import Medicine # Assuming models.medicine.Medicine is your Medicine model
from models.batch import Batch # Assuming models.batch.Batch is your Batch model
from models.medicine_audit import MedicineAudit # Assuming models.medicine_audit.MedicineAudit is your MedicineAudit model
from schemas.medicine_usage_history import MedicineUsageHistoryCreate
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

# Helper function for unit conversion (similar to the one in composition_usage_history)
# It's ideal to put this in a shared utility file if multiple CRUDs need it.
def _convert_quantity(quantity: Decimal, from_unit: str, to_unit: str) -> Decimal:
    """
    Helper function to convert a quantity from one unit to another.
    Supported units for medicine: 'kg', 'gram'.
    """
    if from_unit == to_unit:
        return quantity

    # Convert source unit to a common base (grams)
    quantity_in_grams = quantity
    if from_unit == 'kg':
        quantity_in_grams *= 1000
    elif from_unit == 'gram':
        pass  # Already in grams
    else:
        raise ValueError(f"Unsupported 'from' unit for conversion: {from_unit}")

    # Convert from grams to target unit
    if to_unit == 'kg':
        return quantity_in_grams / 1000
    elif to_unit == 'gram':
        return quantity_in_grams
    else:
        raise ValueError(f"Unsupported 'to' unit for conversion: {to_unit}")


def use_medicine(
    db: Session,
    medicine_id: int,
    batch_id: int,
    used_quantity_grams: Decimal, # Expect this always in grams
    used_at: datetime,
    changed_by: str = None
):
    """
    Records medicine usage, reduces medicine stock, and creates an audit record.
    All internal calculations for audit are in GRAMS.
    """
    medicine = db.query(Medicine).filter(Medicine.id == medicine_id).first()
    if not medicine:
        raise ValueError(f"Medicine with ID {medicine_id} not found.")

    old_medicine_quantity = medicine.quantity
    old_medicine_unit = medicine.unit

    # Convert old medicine quantity to GRAMS for consistent auditing
    old_quantity_for_audit_grams = _convert_quantity(old_medicine_quantity, old_medicine_unit, 'gram')

    # Convert the used_quantity_grams to the medicine's current unit for subtraction
    quantity_to_reduce_in_medicine_unit = _convert_quantity(
        used_quantity_grams,
        'gram', # Input is always in grams
        old_medicine_unit
    )

    # Update medicine quantity
    if medicine.quantity < quantity_to_reduce_in_medicine_unit:
        raise ValueError("Not enough medicine in stock.")
        
    medicine.quantity -= quantity_to_reduce_in_medicine_unit
    db.add(medicine)
    db.flush() # Flush to get the updated quantity for audit

    # Recalculate new quantity in GRAMS for auditing
    new_quantity_for_audit_grams = _convert_quantity(medicine.quantity, medicine.unit, 'gram')
    change_amount_for_audit_grams = new_quantity_for_audit_grams - old_quantity_for_audit_grams # This will be negative

    # Record medicine usage history
    usage = MedicineUsageHistory(
        medicine_id=medicine_id,
        batch_id=batch_id,
        used_quantity_grams=used_quantity_grams, # Store actual used grams
        used_at=used_at,
        changed_by=changed_by
    )
    db.add(usage)

    # Get batch and medicine names for audit note
    batch_obj = db.query(Batch).filter(Batch.id == batch_id).first()
    shed_no = batch_obj.shed_no if batch_obj else "N/A"
    medicine_name = medicine.title if medicine else "N/A"

    # Create MedicineAudit record
    audit = MedicineAudit(
        medicine_id=medicine.id,
        change_type="medicine_usage",
        change_amount=change_amount_for_audit_grams, # Store in grams
        old_weight=old_quantity_for_audit_grams,     # Store in grams
        new_weight=new_quantity_for_audit_grams,   # Store in grams
        changed_by=changed_by,
        note=f"Used {used_quantity_grams} grams of '{medicine_name}' for batch '{shed_no}'."
    )
    db.add(audit)

    db.commit()
    db.refresh(usage) # Refresh to get the ID
    return usage


def get_medicine_usage_history(db: Session, medicine_id: int = None):
    """
    Retrieves medicine usage history, optionally filtered by medicine_id.
    """
    query = db.query(MedicineUsageHistory)
    if medicine_id:
        query = query.filter(MedicineUsageHistory.medicine_id == medicine_id)
    usage_list = query.order_by(MedicineUsageHistory.used_at.desc()).all()

    result = []
    for usage in usage_list:
        medicine = db.query(Medicine).filter(Medicine.id == usage.medicine_id).first()
        batch = db.query(Batch).filter(Batch.id == usage.batch_id).first()

        usage_dict = usage.__dict__.copy()
        usage_dict.pop('_sa_instance_state', None)

        usage_dict['medicine_name'] = medicine.title if medicine else None
        usage_dict['shed_no'] = batch.shed_no if batch else None

        result.append(usage_dict)
    return result


def revert_medicine_usage(db: Session, usage_id: int, changed_by: str = None):
    """
    Reverts a specific medicine usage, adding back quantities and auditing the reversal.
    """
    usage_to_revert = db.query(MedicineUsageHistory).filter(MedicineUsageHistory.id == usage_id).first()
    if not usage_to_revert:
        return False, "Medicine usage record not found."

    medicine_id = usage_to_revert.medicine_id
    used_quantity_grams = usage_to_revert.used_quantity_grams

    medicine = db.query(Medicine).filter(Medicine.id == medicine_id).first()
    if not medicine:
        db.rollback() # Rollback if medicine is missing to prevent partial revert
        return False, f"Associated medicine with ID {medicine_id} not found."

    old_medicine_quantity = medicine.quantity
    old_medicine_unit = medicine.unit

    # Convert old medicine quantity to GRAMS for consistent auditing
    old_quantity_for_audit_grams = _convert_quantity(old_medicine_quantity, old_medicine_unit, 'gram')

    # Convert the used_quantity_grams (to be added back) to the medicine's current unit for addition
    quantity_to_add_in_medicine_unit = _convert_quantity(
        used_quantity_grams,
        'gram', # Input is always in grams
        old_medicine_unit
    )

    # Add back the quantity to the medicine
    medicine.quantity += quantity_to_add_in_medicine_unit
    db.add(medicine)
    db.flush() # Flush to get the updated quantity for audit

    # Recalculate new quantity in GRAMS for auditing
    new_quantity_for_audit_grams = _convert_quantity(medicine.quantity, medicine.unit, 'gram')
    change_amount_for_audit_grams = new_quantity_for_audit_grams - old_quantity_for_audit_grams # This will be positive

    # Get batch and medicine names for audit note
    batch_obj = db.query(Batch).filter(Batch.id == usage_to_revert.batch_id).first()
    shed_no = batch_obj.shed_no if batch_obj else "N/A"
    medicine_name = medicine.title if medicine else "N/A"

    # Create MedicineAudit record for the reversal
    audit = MedicineAudit(
        medicine_id=medicine.id,
        change_type="medicine_revert",
        change_amount=change_amount_for_audit_grams, # Store in grams
        old_weight=old_quantity_for_audit_grams,     # Store in grams
        new_weight=new_quantity_for_audit_grams,   # Store in grams
        changed_by=changed_by,
        note=f"Reverted usage of {used_quantity_grams} grams of '{medicine_name}' for batch '{shed_no}'."
    )
    db.add(audit)

    # Delete the original usage history record
    db.delete(usage_to_revert)
    db.commit()
    return True, "Medicine usage reverted successfully."