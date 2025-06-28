from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from schemas.egg_room_reports import EggRoomReportCreate, EggRoomReportUpdate, EggRoomReportResponse
import crud

router = APIRouter(prefix="/egg-reports", tags=["egg_room_reports"])

@router.get("/{report_date}", response_model=EggRoomReportResponse)
def get_report(report_date: str, db: Session = Depends(get_db)):
    report = crud.get_report_by_date(db, report_date)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report

@router.post("/", response_model=EggRoomReportResponse)
def create_report(report: EggRoomReportCreate, db: Session = Depends(get_db)):
    return crud.create_report(db, report)

@router.put("/{report_date}", response_model=EggRoomReportResponse)
def update_report(report_date: str, report: EggRoomReportUpdate, db: Session = Depends(get_db)):
    return crud.update_report(db, report_date, report)

@router.delete("/{report_date}")
def delete_report(report_date: str, db: Session = Depends(get_db)):
    return crud.delete_report(db, report_date)