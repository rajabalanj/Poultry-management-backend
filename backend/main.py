from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
import auth
import time
import io
from schemas import bovanswhitelayerperformance
from schemas.feed import Feed as FeedSchema
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
from schemas.app_config import AppConfigCreate, AppConfigUpdate, AppConfigOut
from crud import app_config as crud_app_config
from typing import List, Optional
from models.daily_batch import DailyBatch as DailyBatchModel
import egg_room_reports
import bovanswhitelayerperformance
from crud.egg_room_reports import get_report_by_date, create_report, update_report, delete_report
from models.egg_room_reports import EggRoomReport
from schemas.egg_room_reports import EggRoomReportCreate, EggRoomReportUpdate, EggRoomReportResponse
from models.feed_audit import FeedAudit
from models.feed import Feed
from decimal import Decimal



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


app = FastAPI()

#app.mount("/", StaticFiles(directory="dist", html=True), name="static")


allowed_origins_str = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://51.21.190.170,https://51.21.190.170"
)

# Split the string into a list, stripping any whitespace
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(',')]

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # This will now include your production IP
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


#app.mount("/", StaticFiles(directory="dist", html=True), name="static")
app.include_router(reports.router)
app.include_router(auth.router)
app.include_router(egg_room_reports.router)
app.include_router(bovanswhitelayerperformance.router)

@app.post("/batches/", response_model=BatchSchema)
def create_batch(
    batch: BatchCreate, 
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    return crud_batch.create_batch(db=db, batch=batch, changed_by=x_user_id)

@app.get("/batches/")
def read_batches(batch_date: date, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info("Fetching batches with skip=%d, limit=%d, batch_date=%s", skip, limit, batch_date)
    batches = crud_batch.get_all_batches(db, skip=skip, limit=limit, batch_date=batch_date)
    logger.info("Fetched %d batches", len(batches))
    return batches

@app.get("/batches/{batch_id}", response_model=BatchSchema)
def read_batch(batch_id: int, db: Session = Depends(get_db)):
    logger.info("Fetching batch with batch_id=%d", batch_id)
    db_batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if db_batch is None:
        logger.warning("Batch with batch_id=%d not found", batch_id)
        raise HTTPException(status_code=404, detail="Batch not found")
    logger.info("Fetched batch: %s", db_batch)
    return db_batch

@app.patch("/batches/{batch_id}", response_model=BatchSchema)
def update_batch(
    batch_id: int,
    batch_data: dict,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    from utils import calculate_age_progression
    db_batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if db_batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")

    changes = {}
    old_date = db_batch.date
    new_date = batch_data.get("date")
    date_changed_and_increased = False
    if new_date:
        # Convert to date if string
        if isinstance(new_date, str):
            from dateutil import parser
            new_date = parser.parse(new_date).date()
        if new_date > old_date:
            date_changed_and_increased = True

    for key, value in batch_data.items():
        if hasattr(db_batch, key):
            old_value = getattr(db_batch, key)
            if old_value != value:
                changes[key] = {"old": old_value, "new": value}
                setattr(db_batch, key, value)

    if changes:
        # If date increased, delete old daily_batch entries and create one for new_date if not present
        if date_changed_and_increased:
            db.query(DailyBatchModel).filter(
                DailyBatchModel.batch_id == batch_id,
                DailyBatchModel.batch_date < new_date
            ).delete(synchronize_session=False)
            db.commit()
            exists = db.query(DailyBatchModel).filter(
                DailyBatchModel.batch_id == batch_id,
                DailyBatchModel.batch_date == new_date
            ).first()
            if not exists:
                db_daily = DailyBatchModel(
                    batch_id=batch_id,
                    shed_no=db_batch.shed_no,
                    batch_no=db_batch.batch_no,
                    upload_date=new_date,
                    batch_date=new_date,
                    age=db_batch.age,
                    opening_count=db_batch.opening_count,
                    mortality=0,
                    culls=0,
                    table_eggs=0,
                    jumbo=0,
                    cr=0,
                    is_chick_batch=db_batch.is_chick_batch
                )
                db.add(db_daily)
                db.commit()
        # Example: update daily_batch if certain fields changed
        if "shed_no" in changes or "batch_no" in changes:
            related_batches = db.query(DailyBatchModel).filter(DailyBatchModel.batch_id == batch_id).all()
            for rel in related_batches:
                if "shed_no" in changes:
                    rel.shed_no = changes["shed_no"]["new"]
                if "batch_no" in changes:
                    rel.batch_no = changes["batch_no"]["new"]
        # Age update logic for daily_batch
        if "age" in batch_data and new_date:
            target_row = db.query(DailyBatchModel).filter(
                DailyBatchModel.batch_id == batch_id,
                DailyBatchModel.batch_date == new_date
            ).first()
            if target_row:
                try:
                    new_age = float(batch_data["age"])
                except Exception:
                    new_age = 0.0
                target_row.age = str(round(new_age, 1))
                subsequent_rows = db.query(DailyBatchModel).filter(
                    DailyBatchModel.batch_id == batch_id,
                    DailyBatchModel.batch_date > new_date
                ).order_by(DailyBatchModel.batch_date.asc()).all()
                prev_date = new_date
                prev_age = new_age
                for row in subsequent_rows:
                    days_diff = (row.batch_date - prev_date).days
                    prev_age = calculate_age_progression(prev_age, days_diff)
                    row.age = str(round(prev_age, 1))
                    prev_date = row.batch_date
        # Opening count update logic for daily_batch
        if "opening_count" in batch_data and new_date:
            # Update opening_count for the given batch_id and batch_date
            target_row = db.query(DailyBatchModel).filter(
                DailyBatchModel.batch_id == batch_id,
                DailyBatchModel.batch_date == new_date
            ).first()
            if target_row:
                target_row.opening_count = batch_data["opening_count"]
                # Fetch all daily_batch rows for this batch_id ordered by batch_date
                all_rows = db.query(DailyBatchModel).filter(
                    DailyBatchModel.batch_id == batch_id
                ).order_by(DailyBatchModel.batch_date.asc()).all()
                # Find the index of the updated row
                idx = next((i for i, row in enumerate(all_rows) if row.batch_date == new_date), None)
                if idx is not None:
                    prev_row = all_rows[idx]
                    for next_row in all_rows[idx+1:]:
                        next_row.opening_count = prev_row.closing_count  # closing_count is a hybrid property
                        prev_row = next_row
        # Optional: insert change logs into audit table here
        # insert_audit_logs(batch_id, changes, x_user_id)
        db.commit()
        db.refresh(db_batch)

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
    feed: FeedSchema, 
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
    changed_by: str = None
):
    """Update an existing feed."""
    db_feed = db.query(Feed).filter(Feed.id == feed_id).first()
    if not db_feed:
        return None

    old_quantity = db_feed.quantity
    new_quantity = feed_data.get("quantity", old_quantity)

    # Update the provided fields
    for key, value in feed_data.items():
        setattr(db_feed, key, value)
    
    db.commit()
    db.refresh(db_feed)

    # Audit only if quantity changed
    if old_quantity != new_quantity:
        new_quantity_decimal = Decimal(new_quantity)  # Convert new_quantity to Decimal
        audit = FeedAudit(
            feed_id=feed_id,
            change_type="manual",
            change_amount=new_quantity_decimal - old_quantity,
            old_weight=old_quantity,
            new_weight=new_quantity_decimal,
            changed_by=changed_by,
            note="Manual edit"
        )
        db.add(audit)
        db.commit()

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

@app.post("/daily-batch/upload-excel/")
def upload_daily_batch_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload and process an Excel file for daily batch data (only daily_batch, no batch insert)."""
    try:
        contents = file.file.read()
        df = pd.read_excel(io.BytesIO(contents), header=None)

        # Get all shed_nos present in batch table
        all_batches = db.query(Batch).all()
        valid_shed_nos = {b.shed_no for b in all_batches}

        date_indices = df.index[df[0] == 'DATE'].tolist()
        if not date_indices:
            raise HTTPException(status_code=400, detail="No 'DATE' rows found in the Excel file.")

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
                try:
                    batch_id_excel = int(row[0])
                except (ValueError, TypeError):
                    continue
                if pd.isna(row[0]) or pd.isna(row[1]) or pd.isna(row[2]) or pd.isna(row[3]):
                    logger.warning(f"Skipping row {row_idx} (Date: {report_date}) due to missing essential data: {row.tolist()}")
                    continue
                shed_no_excel = str(row[1]).strip()
                if shed_no_excel not in valid_shed_nos:
                    logger.warning(f"Skipping row {row_idx} (Date: {report_date}) due to shed_no not in batch table: {shed_no_excel}")
                    continue
                batch_obj = db.query(Batch).filter(Batch.shed_no == shed_no_excel).first()
                batch_id_for_daily_batch = batch_obj.id if batch_obj else None
                if not batch_id_for_daily_batch:
                    logger.error(f"No batch_id found for shed_no '{shed_no_excel}'. Skipping daily_batch row {row_idx}.")
                    continue
                age_excel = str(row[2]) if pd.notna(row[2]) else ''
                opening_count_excel = int(row[3]) if pd.notna(row[3]) else 0
                mortality_excel = int(row[4]) if pd.notna(row[4]) else 0
                culls_excel = int(row[5]) if pd.notna(row[5]) else 0
                table_eggs_excel = int(row[7]) if pd.notna(row[7]) else 0
                jumbo_excel = int(row[8]) if pd.notna(row[8]) else 0
                cr_excel = int(row[9]) if pd.notna(row[9]) else 0
                closing_count_calculated = opening_count_excel - (mortality_excel + culls_excel)
                hd_calculated = 0.0
                total_eggs_produced_daily = table_eggs_excel + jumbo_excel + cr_excel
                if closing_count_calculated > 0:
                    hd_calculated = float(total_eggs_produced_daily) / closing_count_calculated
                is_chick_batch_calculated = (total_eggs_produced_daily == 0)
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
                crud_daily_batch.create_daily_batch(db=db, daily_batch_data=daily_batch_instance)
                processed_records_count += 1
        return {"message": f"File '{file.filename}' processed and {processed_records_count} daily batch records inserted."}
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unhandled error during Excel upload: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process file: {e}")
    
@app.patch("/daily-batch/{batch_id}/{batch_date}", response_model=DailyBatchUpdate)
def update_daily_batch(
    batch_id: int,
    batch_date: str,
    payload: dict,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    """Update a daily batch row by batch_id and batch_date. Applies propagation logic for age, counts."""
    from models.daily_batch import DailyBatch as DailyBatchModel
    from sqlalchemy import and_
    import dateutil.parser

    # Parse date string
    try:
        batch_date_obj = dateutil.parser.parse(batch_date).date()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid batch_date format")

    # Fetch the current row
    daily_batch = db.query(DailyBatchModel).filter(
        and_(
            DailyBatchModel.batch_id == batch_id,
            DailyBatchModel.batch_date == batch_date_obj
        )
    ).first()

    if not daily_batch:
        raise HTTPException(status_code=404, detail="Daily batch not found")

    # Update shed_no for all rows in batch if present
    if "shed_no" in payload:
        new_shed_no = payload["shed_no"]
        db.query(DailyBatchModel).filter(
            DailyBatchModel.batch_id == batch_id
        ).update({DailyBatchModel.shed_no: new_shed_no})
        daily_batch.shed_no = new_shed_no

    # Propagate age update if present
    if "age" in payload:
        try:
            from utils import calculate_age_progression  # Adjust import as needed
            new_age = float(payload["age"])
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid age value")

        daily_batch.age = str(round(new_age, 1))

        subsequent_rows = db.query(DailyBatchModel).filter(
            DailyBatchModel.batch_id == batch_id,
            DailyBatchModel.batch_date > daily_batch.batch_date
        ).order_by(DailyBatchModel.batch_date.asc()).all()

        prev_date = daily_batch.batch_date
        prev_age = new_age

        for row in subsequent_rows:
            days_diff = (row.batch_date - prev_date).days
            prev_age = calculate_age_progression(prev_age, days_diff)
            row.age = str(prev_age)
            prev_date = row.batch_date


    # Propagate mortality/culls change if either is present
    if "mortality" in payload or "culls" in payload:
        if "mortality" in payload:
            daily_batch.mortality = payload["mortality"]
        if "culls" in payload:
            daily_batch.culls = payload["culls"]
        # Do NOT assign to closing_count (hybrid property)

        # Propagate to subsequent rows
        subsequent_rows = db.query(DailyBatchModel).filter(
            DailyBatchModel.batch_id == batch_id,
            DailyBatchModel.batch_date > daily_batch.batch_date
        ).order_by(DailyBatchModel.batch_date.asc()).all()

        prev_closing = daily_batch.opening_count - (daily_batch.mortality + daily_batch.culls)
        for row in subsequent_rows:
            row.opening_count = prev_closing
            row_closing = row.opening_count - (row.mortality + row.culls)
            prev_closing = row_closing
            # Do NOT assign to row.closing_count

    # Propagate opening_count change if present
    if "opening_count" in payload:
        daily_batch.opening_count = payload["opening_count"]
        # Do NOT assign to closing_count (hybrid property)

        subsequent_rows = db.query(DailyBatchModel).filter(
            DailyBatchModel.batch_id == batch_id,
            DailyBatchModel.batch_date > daily_batch.batch_date
        ).order_by(DailyBatchModel.batch_date.asc()).all()

        prev_closing = daily_batch.opening_count - (daily_batch.mortality + daily_batch.culls)
        for row in subsequent_rows:
            row.opening_count = prev_closing
            row_closing = row.opening_count - (row.mortality + row.culls)
            prev_closing = row_closing
            # Do NOT assign to row.closing_count

    # Update simple fields (no propagation)
    for key in ("table_eggs", "cr", "jumbo"):
        if key in payload:
            setattr(daily_batch, key, payload[key])

    # Update other allowed fields dynamically (excluding ones already handled)
    excluded_fields = {"shed_no", "age", "mortality", "culls", "opening_count", "table_eggs", "cr", "jumbo", "closing_count", "total_eggs", "hd", "standard_hen_day_percentage"}
    for key, value in payload.items():
        if key not in excluded_fields and hasattr(daily_batch, key):
            setattr(daily_batch, key, value)

    db.commit()
    db.refresh(daily_batch)
    return daily_batch

@app.post("/configurations/", response_model=AppConfigOut)
def create_config(config: AppConfigCreate, db: Session = Depends(get_db)):
    return crud_app_config.create_config(db, config)


@app.get("/configurations/", response_model=List[AppConfigOut])
def get_configs(name: Optional[str] = None, db: Session = Depends(get_db)):
    configs = crud_app_config.get_config(db, name)
    # Always return a list, even if empty
    return [configs] if name and configs else configs or []

@app.patch("/configurations/{name}/", response_model=AppConfigOut)
def update_config(name: str, config: AppConfigUpdate, db: Session = Depends(get_db)):
    updated = crud_app_config.update_config_by_name(db, name, config)
    if not updated:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return updated


from typing import List
from fastapi import Query

@app.get("/daily-batch/", response_model=List[dict])
def get_daily_batches(
    batch_date: date = Query(..., description="Date for which to fetch daily batches"),
    db: Session = Depends(get_db)
):
    """
    Fetch all daily_batch rows for a given batch_date. If none exist, generate them and return.
    If batch_date is before a batch's start date, return a message for that batch.
    """
    from models.daily_batch import DailyBatch as DailyBatchModel
    from models.batch import Batch as BatchModel
    from utils import calculate_age_progression
    
    # Try to fetch existing daily_batch rows for the date
    daily_batches = db.query(DailyBatchModel).filter(DailyBatchModel.batch_date == batch_date).all()
    if daily_batches:
        result = []
        for daily in daily_batches:
            d = daily.__dict__.copy()
            d['closing_count'] = daily.closing_count  # access the hybrid property
            d['hd'] = daily.hd
            d['total_eggs'] = daily.total_eggs
            d.pop('_sa_instance_state', None)
            result.append(d)
        return result
    
    # If not found, generate them (same logic as /daily-batch/generate/)
    today = date.today()
    created = []
    batches = db.query(BatchModel).all()
    for batch in batches:
        # If batch_date is before batch's start date, skip and add message
        if batch_date < batch.date:
            created.append({
                "batch_id": batch.id,
                "shed_no": batch.shed_no,
                "batch_no": batch.batch_no,
                "message": "Please modify batch start date in configuration screen to create batch for this date.",
                "batch_start_date": batch.date.isoformat(),
                "requested_date": batch_date.isoformat()
            })
            continue
        # Find the most recent previous daily_batch for this batch
        prev_daily = db.query(DailyBatchModel).filter(
            DailyBatchModel.batch_id == batch.id,
            DailyBatchModel.batch_date < batch_date
        ).order_by(DailyBatchModel.batch_date.desc()).first()

        if prev_daily:
            opening_count = prev_daily.closing_count  # hybrid property
            try:
                prev_age = float(prev_daily.age)
            except Exception:
                prev_age = 0.0
            days_diff = (batch_date - prev_daily.batch_date).days
            age = calculate_age_progression(prev_age, days_diff)
        else:
            opening_count = batch.opening_count
            try:
                age = float(batch.age)
            except Exception:
                age = 0.0

        db_daily = DailyBatchModel(
            batch_id=batch.id,
            shed_no=batch.shed_no,
            batch_no=batch.batch_no,
            upload_date=today,
            batch_date=batch_date,
            age=str(round(age, 1)),
            opening_count=opening_count,
            mortality=0,
            culls=0,
            table_eggs=0,
            jumbo=0,
            cr=0,
            is_chick_batch=getattr(batch, "is_chick_batch", False)
        )
        db.add(db_daily)
        db.commit()
        db.refresh(db_daily)
        d = db_daily.__dict__.copy()
        d['closing_count'] = db_daily.closing_count  # access the hybrid property
        d['hd'] = db_daily.hd
        d['total_eggs'] = db_daily.total_eggs
        d.pop('_sa_instance_state', None)
        created.append(d)
    return created

@app.get("/batches/all/", response_model=List[BatchSchema])
def get_all_batches(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Fetch all batches with pagination (no batch_date required).
    """
    try:
        batches = db.query(Batch).offset(skip).limit(limit).all()
        return batches
    except Exception as e:
        logger.exception(f"Error fetching batches (skip={skip}, limit={limit}): {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching batches.")

@app.get("/feed/{feed_id}/audit/", response_model=List[dict])
def get_feed_audit(feed_id: int, db: Session = Depends(get_db)):
    audits = db.query(FeedAudit).filter(FeedAudit.feed_id == feed_id).order_by(FeedAudit.timestamp.desc()).all()
    return [
        {
            "timestamp": a.timestamp,
            "change_type": a.change_type,
            "change_amount": a.change_amount,
            "old_weight": a.old_weight,
            "new_weight": a.new_weight,
            "changed_by": a.changed_by,
            "note": a.note,
        }
        for a in audits
    ]
