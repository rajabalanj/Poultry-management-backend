from sqlalchemy.orm import Session
from models.egg_room_reports import EggRoomReport
from schemas.egg_room_reports import EggRoomReportCreate, EggRoomReportUpdate
from fastapi import HTTPException

def get_report_by_date(db: Session, report_date: str):
    return db.query(EggRoomReport).filter(EggRoomReport.report_date == report_date).first()

def create_report(db: Session, report: EggRoomReportCreate):
    db_report = EggRoomReport(**report.dict())
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report

def update_report(db: Session, report_date: str, report: EggRoomReportUpdate):
    db_report = db.query(EggRoomReport).filter(EggRoomReport.report_date == report_date).first()
    if not db_report:
        return None
    for key, value in report.dict(exclude_unset=True).items():
        setattr(db_report, key, value)
    db.commit()
    db.refresh(db_report)
    return db_report

def delete_report(db: Session, report_date: str):
    db_report = db.query(EggRoomReport).filter(EggRoomReport.report_date == report_date).first()
    if not db_report:
        return None
    db.delete(db_report)
    db.commit()
    return {"message": "Report deleted"}