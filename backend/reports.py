from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta, date
from models.daily_batch import DailyBatch
from database import get_db
import pandas as pd
from io import BytesIO
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy import and_
import models 

def get_daily_batches_by_date_range(db: Session, start_date: date, end_date: date):
    return db.query(models.DailyBatch).filter(
        and_(models.DailyBatch.batch_date >= start_date,
             models.DailyBatch.batch_date <= end_date)
    ).all()

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
)

@router.get("/daily-report")
def get_daily_report(start_date: Optional[str] = None, end_date: Optional[str] = None, db: Session = Depends(get_db)):
    if not start_date or not end_date:
        raise HTTPException(status_code=400, detail="Both start_date and end_date parameters are required")

    try:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Please use YYYY-MM-DD for both start_date and end_date")

    if start_date_obj > end_date_obj:
        raise HTTPException(status_code=400, detail="Start date cannot be after the end date")

    daily_data = get_daily_batches_by_date_range(db, start_date=start_date_obj, end_date=end_date_obj)

    if not daily_data:
        raise HTTPException(status_code=200, detail=f"No data found between {start_date} and {end_date}")
    
    report_list = [item.__dict__ for item in daily_data]
    for item in report_list:
        del item['_sa_instance_state']  # Remove SQLAlchemy internal attribute

    # Create a pandas DataFrame
    df = pd.DataFrame(report_list)

    # Create an in-memory Excel file
    excel_file = BytesIO()
    df.to_excel(excel_file, index=False, sheet_name='Daily Report')
    excel_file.seek(0)

    # Prepare the response
    headers = {
        'Content-Disposition': 'attachment; filename="daily_report.xlsx"'
    }

    return StreamingResponse(excel_file, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers=headers)

@router.get("/snapshot")
def get_snapshot(start_date: str, end_date: str, batch_id: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Get a snapshot of batches between the specified start_date and end_date with total_eggs count.
    Optionally filter by batch_id.
    """
    try:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Please use YYYY-MM-DD for both start_date and end_date")

    if start_date_obj > end_date_obj:
        raise HTTPException(status_code=400, detail="Start date cannot be after the end date")

    # Query DailyBatch for the specified date range
    query = db.query(DailyBatch).filter(
        DailyBatch.batch_date >= start_date_obj,
        DailyBatch.batch_date <= end_date_obj
    )

    if batch_id is not None:
        query = query.filter(DailyBatch.batch_id == batch_id)

    daily_batches = query.all()

    # Serialize the data, including total_eggs
    result = [
        {
            "batch_id": batch.batch_id,
            "batch_no": batch.batch_no,
            "batch_date": batch.batch_date,
            "shed_no": batch.shed_no,
            "age": batch.age,
            "opening_count": batch.opening_count,
            "mortality": batch.mortality,
            "culls": batch.culls,
            "closing_count": batch.closing_count,
            "table": batch.table,
            "jumbo": batch.jumbo,
            "cr": batch.cr,
            "total_eggs": batch.total_eggs  # Computed property
        }
        for batch in daily_batches
    ]

    return JSONResponse(content=result)

