from sqlalchemy.orm import Session
from models.egg_room_reports import EggRoomReport
from schemas.egg_room_reports import EggRoomReportCreate, EggRoomReportUpdate
from fastapi import HTTPException

def get_report_by_date(db: Session, report_date):
    return db.query(EggRoomReport).filter(EggRoomReport.report_date == report_date).first()

def create_report(db: Session, report: EggRoomReportCreate):
    db_report = EggRoomReport(**report.dict())
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report

def update_report(db: Session, report_date, report_update: EggRoomReportUpdate):
    db_report = get_report_by_date(db, report_date)
    if not db_report:
        raise HTTPException(status_code=404, detail="Report not found")
    for key, value in report_update.dict(exclude_unset=True).items():
        setattr(db_report, key, value)
    db.commit()
    db.refresh(db_report)
    return db_report

def delete_report(db: Session, report_date):
    db_report = get_report_by_date(db, report_date)
    if not db_report:
        raise HTTPException(status_code=404, detail="Report not found")
    db.delete(db_report)
    db.commit()
    return {"detail": "Report deleted"}