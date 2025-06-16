from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from scheduler import scheduler  # Import the configured scheduler
import time
import io
from schemas.feed import Feed
from database import Base, SessionLocal, engine
from contextlib import asynccontextmanager
from datetime import datetime, time as dt_time, timedelta
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
from schemas.batch import Batch as BatchSchema
# from schemas.batch_history import BatchHistory
import crud.batch as crud_batch
import crud.feed as crud_feed
# import crud.batch_history as crud_history
from datetime import date
import logging
from dateutil import parser
from schemas.daily_batch import DailyBatchCreate, DailyBatchUpdate
import crud.daily_batch as crud_daily_batch
import pandas as pd
from models.batch import Batch

# --- Logging Configuration (Add this section) ---
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True) # Create 'logs' directory if it doesn't exist

# Create a unique log file name based on current date/time
current_time_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = os.path.join(LOG_DIR, f"app_{current_time_str}.log")

# Configure the root logger
logging.basicConfig(
    level=logging.INFO, # Set desired minimum log level (INFO, DEBUG, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=LOG_FILE, # Log to a file
    filemode='a' # Append to the file if it exists
)

# Optional: Also add a StreamHandler to output logs to the console
# This allows you to see logs in both the file and the terminal
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO) # Console can have a different log level if needed
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(console_handler) # Add to the root logger

# Get a logger for this module (app.main)
logger = logging.getLogger(__name__)
logger.info("Application starting up...")
# --- End Logging Configuration ---


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

@app.post("/batches/", response_model=BatchSchema)
def create_batch(
    batch: BatchCreate, 
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    return crud_batch.create_batch(db=db, batch=batch, changed_by=x_user_id)

@app.get("/batches/", response_model=List[BatchSchema])
def read_batches(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info("Fetching batches with skip=%d and limit=%d", skip, limit)
    batches = crud_batch.get_all_batches(db, skip=skip, limit=limit)
    logger.info("Fetched %d batches", len(batches))
    return batches

@app.get("/batches/fallback/", response_model=List[BatchSchema])
def read_batches_fallback(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info("Fetching batches with fallback logic, skip=%d, limit=%d", skip, limit)
    batches = crud_batch.get_all_batches(db, skip=skip, limit=limit)
    from models.daily_batch import DailyBatch as DailyBatchModel

    result = []
    for batch in batches:
        total_eggs = (batch.table_eggs or 0) + (batch.jumbo or 0) + (batch.cr or 0)
        if total_eggs == 0 and batch.closing_count == batch.opening_count:
            # Look for the most recent daily_batch with eggs or mortality/culls
            daily_batches = (
                db.query(DailyBatchModel)
                .filter(DailyBatchModel.batch_id == batch.id)
                .order_by(DailyBatchModel.batch_date.desc())
                .all()
            )
            found = False
            for daily in daily_batches:
                daily_total_eggs = (daily.table_eggs or 0) + (daily.jumbo or 0) + (daily.cr or 0)
                if daily_total_eggs > 0 or daily.closing_count != daily.opening_count:
                    logger.info("Fallback: Found daily_batch for batch_id=%d on %s", batch.id, daily.batch_date)
                    result.append(BatchSchema(
                        id=daily.batch_id,
                        shed_no=daily.shed_no,
                        batch_no=daily.batch_no,
                        date=daily.batch_date,
                        age=daily.age,
                        opening_count=daily.opening_count,
                        mortality=daily.mortality,
                        culls=daily.culls,
                        closing_count=daily.closing_count,
                        table_eggs=daily.table_eggs,
                        jumbo=daily.jumbo,
                        cr=daily.cr,
                        hd=getattr(daily, "hd", None),
                        is_chick_batch=getattr(daily, "is_chick_batch", None),
                    ))
                    found = True
                    break
            if not found:
                result.append(batch)
        else:
            result.append(batch)
    logger.info("Fetched %d batches with fallback logic", len(result))
    return result

@app.get("/batches/{batch_id}", response_model=BatchSchema)
def read_batch(batch_id: int, db: Session = Depends(get_db)):
    logger.info("Fetching batch with batch_id=%d", batch_id)
    db_batch = crud_batch.get_batch(db, batch_id=batch_id)
    if db_batch is None:
        logger.warning("Batch with batch_id=%d not found", batch_id)
        raise HTTPException(status_code=404, detail="Batch not found")
    logger.info("Fetched batch: %s", db_batch)
    return db_batch

@app.get("/batches/{batch_id}/fallback", response_model=BatchSchema)
def read_batch_fallback(batch_id: int, db: Session = Depends(get_db)):
    logger.info("Fetching batch with batch_id=%d", batch_id)
    db_batch = crud_batch.get_batch(db, batch_id=batch_id)
    if db_batch is None:
        logger.warning("Batch with batch_id=%d not found", batch_id)
        raise HTTPException(status_code=404, detail="Batch not found")
    logger.info("Fetched batch: %s", db_batch)

    # If total_eggs is zero, look for the most recent daily_batch with total_eggs > 0
    if (db_batch.table_eggs + db_batch.jumbo + db_batch.cr) == 0 and db_batch.closing_count == db_batch.opening_count:
        logger.info("No eggs found and no mortality and culls for batch_id=%d, looking for daily_batch table in batch %d, searching daily_batch table...", batch_id)
        from models.daily_batch import DailyBatch as DailyBatchModel
        daily_batches = (
            db.query(DailyBatchModel)
            .filter(DailyBatchModel.batch_id == batch_id)
            .order_by(DailyBatchModel.batch_date.desc())
            .all()
        )
        for daily in daily_batches:
            total_eggs = (daily.table_eggs or 0) + (daily.jumbo or 0) + (daily.cr or 0)
            if total_eggs > 0 or daily.closing_count != daily.opening_count:
                logger.info("Found daily_batch with eggs or mortality/culls for batch_id=%d on %s", batch_id, daily.batch_date)
                # Return a BatchSchema instance with daily_batch data
                return BatchSchema(
                    id=daily.batch_id,
                    shed_no=daily.shed_no,
                    batch_no=daily.batch_no,
                    date=daily.batch_date,
                    age=daily.age,
                    opening_count=daily.opening_count,
                    mortality=daily.mortality,
                    culls=daily.culls,
                    closing_count=daily.closing_count,
                    table_eggs=daily.table_eggs,
                    jumbo=daily.jumbo,
                    cr=daily.cr,
                    hd=getattr(daily, "hd", None),
                    is_chick_batch=getattr(daily, "is_chick_batch", None),
                )
        logger.info("No daily_batch with eggs found for batch_id=%d", batch_id)

    # Return the batch result if total_eggs is not zero or no daily_batch found
    return db_batch

@app.patch("/batches/{batch_id}", response_model=BatchSchema)
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

@app.patch("/compositions/{composition_id}", response_model=Composition)
def patch_composition(composition_id: int, composition: CompositionCreate, db: Session = Depends(get_db)):
    db_composition = crud_composition.update_composition(db, composition_id, composition)
    if db_composition is None:
        raise HTTPException(status_code=404, detail="Composition not found")
    return db_composition

# @app.post("/daily-batch/", response_model=DailyBatch)
# def create_daily_batch(
#     daily_batch: DailyBatchCreate,
#     db: Session = Depends(get_db),
#     x_user_id: Optional[str] = Header(None)
# ):
#     return crud_daily_batch.create_daily_batch(db=db, daily_batch=daily_batch, changed_by=x_user_id)

@app.post("/daily-batch/upload-excel/")
def upload_daily_batch_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload and process an Excel file for daily batch data."""
    try:
        contents = file.file.read()
        # header=None because your Excel has custom header rows that need parsing
        df = pd.read_excel(io.BytesIO(contents), header=None)

        # --- Phase 1: Identify unique sheds and their last-seen data for 'batch' table insertion/update ---
        shed_nos = set()
        # Store the last encountered pandas Series (row) for each shed_no
        shed_no_to_last_row: Dict[str, pd.Series] = {}

        date_indices = df.index[df[0] == 'DATE'].tolist()
        if not date_indices:
            raise HTTPException(status_code=400, detail="No 'DATE' rows found in the Excel file.")

        for i, date_idx in enumerate(date_indices):
            data_start = date_idx + 2
            if i + 1 < len(date_indices):
                data_end = date_indices[i + 1]
            else:
                total_rows = df.index[(df[0] == 'TOTAL') & (df.index > data_start)].tolist()
                data_end = total_rows[0] if total_rows else len(df)

            for row_idx in range(data_start, data_end):
                row = df.iloc[row_idx]

                # Skip empty rows or rows where BATCH (col 0) is 'TOTAL' or NaN
                if pd.isna(row[0]) or str(row[0]).strip().upper() == 'TOTAL':
                    continue
                # Skip rows with missing SHED (col 1), as it's critical for shed_no mapping
                if pd.isna(row[1]):
                    logger.warning(f"Skipping row {row_idx} due to missing shed_no: {row.tolist()}")
                    continue

                shed_no = str(row[1]).strip()
                shed_nos.add(shed_no)
                shed_no_to_last_row[shed_no] = row # Update with the last seen row for this shed_no

        # Fetch all existing shed_no from the 'batch' table
        existing_batches_orms = db.query(Batch).filter(Batch.shed_no.in_(list(shed_nos))).all()
        existing_shed_nos = {b.shed_no for b in existing_batches_orms}

        # Insert missing shed_no into 'batch' table using the last occurring row for each
        batches_to_add: List[Batch] = []
        for shed_no in shed_nos - existing_shed_nos:
            row = shed_no_to_last_row[shed_no] # Get the last row for this new shed_no

            # Safely extract and convert values for 'Batch' table
            opening_count_val = int(row[3]) if pd.notna(row[3]) else 0
            mortality_val = int(row[4]) if pd.notna(row[4]) else 0
            culls_val = int(row[5]) if pd.notna(row[5]) else 0
            table_eggs_val = int(row[7]) if pd.notna(row[7]) else 0
            jumbo_val = int(row[8]) if pd.notna(row[8]) else 0
            cr_val = int(row[9]) if pd.notna(row[9]) else 0
            report_date = pd.to_datetime(df.iloc[date_idx, 1], format='%m-%d-%Y').date()

            calculated_closing_count_batch = opening_count_val - (mortality_val + culls_val)
            total_eggs_produced_batch = table_eggs_val + jumbo_val + cr_val

            hd_calculated_batch = 0.0
            if calculated_closing_count_batch > 0:
                hd_calculated_batch = float(total_eggs_produced_batch) / calculated_closing_count_batch

            is_chick_batch_calculated_batch = (total_eggs_produced_batch == 0)
            batch_id_excel = int(row[0])


            # Create an instance of your Batch ORM model (assuming Batch is your ORM model)
            new_batch = Batch(
                shed_no=shed_no,
                batch_no=f"B-{batch_id_excel:04d}",
                date=report_date,  # Use the date from the Excel, not today's date
                age=str(row[2]) if pd.notna(row[2]) else '',
                opening_count=opening_count_val,
                mortality=mortality_val,
                culls=culls_val,
                closing_count=calculated_closing_count_batch,
                table_eggs=table_eggs_val,
                jumbo=jumbo_val,
                cr=cr_val,
                hd=hd_calculated_batch,
                is_chick_batch=is_chick_batch_calculated_batch,
            )
            batches_to_add.append(new_batch)

        if batches_to_add:
            db.add_all(batches_to_add)
            db.commit()

        # Build shed_no to batch_id mapping (ensure all shed_no are present after potential inserts)
        batch_map = {b.shed_no: b.id for b in db.query(Batch).filter(Batch.shed_no.in_(list(shed_nos))).all()}

        # --- Phase 2: Process all daily batch rows and insert into 'daily_batch' table ---
        # We will now iterate and call create_daily_batch for each record
        processed_records_count = 0

        for i, date_idx in enumerate(date_indices):
            report_date = pd.to_datetime(df.iloc[date_idx, 1], format='%m-%d-%Y').date()
            data_start = date_idx + 2
            if i + 1 < len(date_indices):
                data_end = date_indices[i + 1]
            else:
                total_rows = df.index[(df[0] == 'TOTAL') & (df.index > data_start)].tolist()
                data_end = total_rows[0] if total_rows else len(df)

            for row_idx in range(data_start, data_end):
                row = df.iloc[row_idx]

                if pd.isna(row[0]) or str(row[0]).strip().upper() == 'TOTAL':
                    continue
                if pd.isna(row[0]) or pd.isna(row[1]) or pd.isna(row[2]) or pd.isna(row[3]):
                    logger.warning(f"Skipping row {row_idx} (Date: {report_date}) due to missing essential data: {row.tolist()}")
                    continue

                try:
                    batch_id_excel = int(row[0])
                    shed_no_excel = str(row[1]).strip()
                    age_excel = str(row[2]) if pd.notna(row[2]) else ''
                    opening_count_excel = int(row[3]) if pd.notna(row[3]) else 0
                    mortality_excel = int(row[4]) if pd.notna(row[4]) else 0
                    culls_excel = int(row[5]) if pd.notna(row[5]) else 0
                    table_eggs_excel = int(row[7]) if pd.notna(row[7]) else 0
                    jumbo_excel = int(row[8]) if pd.notna(row[8]) else 0
                    cr_excel = int(row[9]) if pd.notna(row[9]) else 0

                    # Always fetch the batch_id from the database for the current shed_no
                    batch_obj = db.query(Batch).filter(Batch.shed_no == shed_no_excel).first()
                    batch_id_for_daily_batch = batch_obj.id if batch_obj else None
                    if not batch_id_for_daily_batch:
                        logger.error(f"No batch_id found for shed_no '{shed_no_excel}'. Skipping daily_batch row {row_idx}.")
                        continue

                    closing_count_calculated = opening_count_excel - (mortality_excel + culls_excel)
                    
                    hd_calculated = 0.0
                    total_eggs_produced_daily = table_eggs_excel + jumbo_excel + cr_excel
                    if closing_count_calculated > 0:
                        hd_calculated = float(total_eggs_produced_daily) / closing_count_calculated
                    
                    is_chick_batch_calculated = (total_eggs_produced_daily == 0)

                    # Create an instance of your Pydantic DailyBatchCreate model
                    daily_batch_instance = DailyBatchCreate(
                        batch_id=batch_id_for_daily_batch,
                        shed_no=shed_no_excel,
                        batch_no=f"B-{batch_id_excel:04d}",
                        upload_date=date.today(),
                        batch_date=report_date,
                        age=age_excel,
                        opening_count=opening_count_excel,
                        mortality=mortality_excel,
                        culls=culls_excel,
                        closing_count=closing_count_calculated,
                        table_eggs=table_eggs_excel,
                        jumbo=jumbo_excel,
                        cr=cr_excel,
                        hd=hd_calculated,
                        is_chick_batch=is_chick_batch_calculated
                    )
                    
                    # --- CALLING YOUR EXISTING create_daily_batch FUNCTION ---
                    crud_daily_batch.create_daily_batch(db=db, daily_batch_data=daily_batch_instance)
                    processed_records_count += 1

                except ValueError as ve:
                    logger.error(f"Data conversion error in row {row_idx} (Date: {report_date}): {ve}. Row data: {row.tolist()}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error processing row {row_idx} (Date: {report_date}): {e}. Row data: {row.tolist()}")
                    continue

        return {"message": f"File '{file.filename}' processed and {processed_records_count} daily batch records inserted."}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unhandled error during Excel upload: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process file: {e}")