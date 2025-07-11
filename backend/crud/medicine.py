from sqlalchemy.orm import Session
from sqlalchemy import func
from models.medicine import Medicine as MedicineModel
# from schemas.batch import BatchCreate
from datetime import date
from schemas.medicine import Medicine as MedicineSchema

def get_medicine(db: Session, medicine_id: int):
    return db.query(MedicineModel).filter(MedicineModel.id == medicine_id).first()

def get_all_medicines(db: Session, skip: int = 0, limit: int = 100):
    return db.query(MedicineModel).offset(skip).limit(limit).all()

def create_medicine(db: Session, medicine: MedicineModel, changed_by: str = None):
    db_medicine = MedicineModel(
        title=medicine.title,
        createdDate=medicine.createdDate,
        quantity=medicine.quantity,
        unit=medicine.unit,
        warningKGThreshold=medicine.warningKGThreshold,
        warningGramThreshold=medicine.warningGramThreshold,
    )
    db.add(db_medicine)
    db.commit()
    db.refresh(db_medicine)
    return db_medicine

def update_medicine(db: Session, medicine_id: int, medicine_data: dict, changed_by: str = None):
    db_medicine = db.query(MedicineModel).filter(MedicineModel.id == medicine_id).first()
    if not db_medicine:
        return None

    # Update the provided fields
    for key, value in medicine_data.items():
        setattr(db_medicine, key, value)
    
    db.commit()
    db.refresh(db_medicine)
    return db_medicine

def delete_medicine(db: Session, medicine_id: int, changed_by: str = None):
    db_medicine = db.query(MedicineModel).filter(MedicineModel.id == medicine_id).first()
    if not db_medicine:
        return None

    db.delete(db_medicine)
    db.commit()
    return db_medicine