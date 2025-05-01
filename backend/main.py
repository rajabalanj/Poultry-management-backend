from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
import schedule
import time
from trigger_functions import get_all_batch_ids, increment_age, run_eod_tasks, update_opening_count
from database import SessionLocal, engine
from contextlib import asynccontextmanager
from datetime import datetime, time as dt_time
import asyncio
import reports
from database import get_db
from fastapi.staticfiles import StaticFiles 
from fastapi.responses import FileResponse
import os

from database import SessionLocal, engine, Base
from schemas.batch import Batch, BatchCreate
# from schemas.batch_history import BatchHistory
import crud.batch as crud
# import crud.batch_history as crud_history
from datetime import date
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



# Create database tables
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.running = True

    async def run_scheduler_async(app_state):
        while app_state.running:
            schedule.run_pending()
            await asyncio.sleep(1)

    schedule.every().day.at(EOD_TIME.strftime("%H:%M")).do(
        lambda: asyncio.create_task(run_eod_tasks())
    )

    asyncio.create_task(run_scheduler_async(app.state))
    yield
    app.state.running = False

app = FastAPI()

#app.mount("/", StaticFiles(directory="dist", html=True), name="static")


# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


#app.mount("/", StaticFiles(directory="dist", html=True), name="static")
app.include_router(reports.router)



# FASTAPI_URL = "http://localhost:8000/transfer_eod_data/"  # Adjust if needed
EOD_TIME = dt_time(13, 45)  # Set your desired EOD time in IST

def run_scheduler(app_state):
    while app_state["running"]:
        schedule.run_pending()
        time.sleep(1)

@app.post("/batches/", response_model=Batch)
def create_batch(
    batch: BatchCreate, 
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    return crud.create_batch(db=db, batch=batch, changed_by=x_user_id)

@app.get("/batches/", response_model=List[Batch])
def read_batches(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info("Fetching batches with skip=%d and limit=%d", skip, limit)
    batches = crud.get_all_batches(db, skip=skip, limit=limit)
    logger.info("Fetched %d batches", len(batches))
    return batches

@app.get("/batches/{batch_id}", response_model=Batch)
def read_batch(batch_id: int, db: Session = Depends(get_db)):
    db_batch = crud.get_batch(db, batch_id=batch_id)
    if db_batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return db_batch

@app.patch("/batches/{batch_id}", response_model=Batch)
def update_batch(
    batch_id: int, 
    batch_data: dict, 
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    db_batch = crud.update_batch(db, batch_id=batch_id, batch_data=batch_data, changed_by=x_user_id)
    if db_batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return db_batch

@app.delete("/batches/{batch_id}")
def delete_batch(
    batch_id: int, 
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    success = crud.delete_batch(db, batch_id=batch_id, changed_by=x_user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Batch not found")
    return {"message": "Batch deleted successfully"}

@app.get("/reports/batch-report")
def get_batch_report(batch_id: int, db: Session = Depends(get_db)):
    """Generate and return a batch report as an Excel file."""
    # Generate the Excel report (you need to implement this function in `reports.py`)
    file_path = reports.generate_batch_report_excel(batch_id, db)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Report file not found")

    return FileResponse(file_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=f"batch_report_{batch_id}.xlsx")
@app.get("/test")
async def test_route():
    return {"message": "Test route is working!"}

app.mount("/", StaticFiles(directory="dist", html=True), name="static")