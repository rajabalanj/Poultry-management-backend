from sqlalchemy.orm import Session
from models.egg_room_reports import EggRoomReport
from schemas.egg_room_reports import EggRoomReportCreate, EggRoomReportUpdate
from typing import List

def get_report_by_date(db: Session, report_date: str, tenant_id: str):
    return db.query(EggRoomReport).filter(EggRoomReport.report_date == report_date, EggRoomReport.tenant_id == tenant_id).first()

def get_reports_by_date_range(db: Session, start_date: str, end_date: str, tenant_id: str) -> List[EggRoomReport]:
    return (
        db.query(EggRoomReport)
        .filter(
            EggRoomReport.report_date >= start_date,
            EggRoomReport.report_date <= end_date,
            EggRoomReport.tenant_id == tenant_id
        )
        .order_by(EggRoomReport.report_date)
        .all()
    )

def create_report(db: Session, report: EggRoomReportCreate, tenant_id: str) -> EggRoomReport:
    # Calculate opening balances from previous day's closing
    prev_report = db.query(EggRoomReport).filter(
        EggRoomReport.report_date < report.report_date,
        EggRoomReport.tenant_id == tenant_id
    ).order_by(EggRoomReport.report_date.desc()).first()
    
    opening_values = {
        'table_opening': prev_report.table_closing if prev_report else 0,
        'jumbo_opening': prev_report.jumbo_closing if prev_report else 0,
        'grade_c_opening': prev_report.grade_c_closing if prev_report else 0
    }
    
    db_report = EggRoomReport(**{**report.dict(), **opening_values, 'tenant_id': tenant_id})
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report

def update_report(db: Session, report_date: str, report: EggRoomReportUpdate, tenant_id: str) -> EggRoomReport:
    """
    Updates an existing egg room report.
    The opening/closing balances of subsequent days are updated automatically on the next read.
    """
    db_report = db.query(EggRoomReport).filter(EggRoomReport.report_date == report_date, EggRoomReport.tenant_id == tenant_id).first()
    if not db_report:
        return None

    for key, value in report.dict(exclude_unset=True).items():
        setattr(db_report, key, value)

    db.commit()
    db.refresh(db_report)
    return db_report

def delete_report(db: Session, report_date: str, tenant_id: str):
    """
    Deletes a report for a specific date.
    """
    db_report = db.query(EggRoomReport).filter(EggRoomReport.report_date == report_date, EggRoomReport.tenant_id == tenant_id).first()
    if not db_report:
        return None
    db.delete(db_report)
    db.commit()
    return {"message": "Report deleted"}