from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from scheduler import scheduler  # Import the configured scheduler
import time
from schemas.feed import Feed
from database import Base, SessionLocal, engine
from contextlib import asynccontextmanager
from datetime import datetime, time as dt_time
import asyncio
import reports
from database import get_db
from fastapi.staticfiles import StaticFiles 
from fastapi.responses import FileResponse
import os
from schemas.compositon import Composition, CompositionCreate
import crud.composition as crud_composition
from crud.composition_usage_history import use_composition, create_composition_usage_history, get_composition_usage_history
from schemas.composition_usage_history import CompositionUsageHistoryCreate, CompositionUsageHistory
from datetime import datetime
from schemas.batch import Batch, BatchCreate
# from schemas.batch_history import BatchHistory
import crud.batch as crud_batch
import crud.feed as crud_feed
# import crud.batch_history as crud_history
from datetime import date
import logging
from dateutil import parser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



# Create database tables
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    print("APScheduler started")
    yield
    scheduler.shutdown()
    print("APScheduler shutdown")
app = FastAPI(lifespan=lifespan)

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

@app.post("/batches/", response_model=Batch)
def create_batch(
    batch: BatchCreate, 
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    return crud_batch.create_batch(db=db, batch=batch, changed_by=x_user_id)

@app.get("/batches/", response_model=List[Batch])
def read_batches(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info("Fetching batches with skip=%d and limit=%d", skip, limit)
    batches = crud_batch.get_all_batches(db, skip=skip, limit=limit)
    logger.info("Fetched %d batches", len(batches))
    return batches

@app.get("/batches/{batch_id}", response_model=Batch)
def read_batch(batch_id: int, db: Session = Depends(get_db)):
    db_batch = crud_batch.get_batch(db, batch_id=batch_id)
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
    db_batch = crud_batch.update_batch(db, batch_id=batch_id, batch_data=batch_data, changed_by=x_user_id)
    if db_batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return db_batch

@app.delete("/batches/{batch_id}")
def delete_batch(
    batch_id: int, 
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    success = crud_batch.delete_batch(db, batch_id=batch_id, changed_by=x_user_id)
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
@app.get("/")
async def test_route():
    return {"message": "Welcome to the FastAPI application!"}

@app.get("/feed/{feed_id}")
def get_feed(feed_id: int, db: Session = Depends(get_db)):
    """Get a specific feed by ID."""
    db_feed = crud_feed.get_feed(db, feed_id=feed_id)
    if db_feed is None:
        raise HTTPException(status_code=404, detail="Feed not found")
    return db_feed

@app.get("/feed/all/")
def get_all_feeds(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all feeds with pagination."""
    feeds = crud_feed.get_all_feeds(db, skip=skip, limit=limit)
    return feeds

@app.post("/feed/")
def create_feed(
    feed: Feed, 
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    """Create a new feed."""
    return crud_feed.create_feed(db=db, feed=feed, changed_by=x_user_id)

@app.patch("/feed/{feed_id}")
def update_feed(
    feed_id: int, 
    feed_data: dict, 
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    """Update an existing feed."""
    db_feed = crud_feed.update_feed(db, feed_id=feed_id, feed_data=feed_data, changed_by=x_user_id)
    if db_feed is None:
        raise HTTPException(status_code=404, detail="Feed not found")
    return db_feed

@app.delete("/feed/{feed_id}")
def delete_feed(
    feed_id: int, 
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    """Delete a specific feed."""
    success = crud_feed.delete_feed(db, feed_id=feed_id, changed_by=x_user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Feed not found")
    return {"message": "Feed deleted successfully"}

@app.post("/compositions/", response_model=Composition)
def create_composition(composition: CompositionCreate, db: Session = Depends(get_db)):
    return crud_composition.create_composition(db, composition)

@app.get("/compositions/{composition_id}", response_model=Composition)
def read_composition(composition_id: int, db: Session = Depends(get_db)):
    db_composition = crud_composition.get_composition(db, composition_id)
    if db_composition is None:
        raise HTTPException(status_code=404, detail="Composition not found")
    return db_composition

@app.get("/compositions/", response_model=List[Composition])
def read_compositions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud_composition.get_compositions(db, skip=skip, limit=limit)

@app.put("/compositions/{composition_id}", response_model=Composition)
def update_composition(composition_id: int, composition: CompositionCreate, db: Session = Depends(get_db)):
    db_composition = crud_composition.update_composition(db, composition_id, composition)
    if db_composition is None:
        raise HTTPException(status_code=404, detail="Composition not found")
    return db_composition

@app.delete("/compositions/{composition_id}")
def delete_composition(composition_id: int, db: Session = Depends(get_db)):
    success = crud_composition.delete_composition(db, composition_id)
    if not success:
        raise HTTPException(status_code=404, detail="Composition not found")
    return {"message": "Composition deleted"}

@app.post("/compositions/use-composition")
def use_composition_endpoint(
    data: dict,
    db: Session = Depends(get_db)
):
    composition_id = data["compositionId"]
    times = data["times"]
    used_at = data.get("usedAt")
    if used_at:
        try:
            used_at_dt = datetime.fromisoformat(used_at)
        except ValueError:
            used_at_dt = parser.parse(used_at)
    else:
        used_at_dt = datetime.now()
    usage = use_composition(db, composition_id, times, used_at_dt)
    return {"message": "Composition used and feed quantities updated", "usage_id": usage.id}

@app.get("/compositions/usage-history", response_model=list[CompositionUsageHistory])
def get_all_composition_usage_history(
    db: Session = Depends(get_db)
):
    return get_composition_usage_history(db)

@app.get("/compositions/{composition_id}/usage-history", response_model=list[CompositionUsageHistory])
def get_composition_usage_history_endpoint(
    composition_id: int,
    db: Session = Depends(get_db)
):
    return get_composition_usage_history(db, composition_id)