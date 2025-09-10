from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File
from dotenv import load_dotenv

load_dotenv()
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import io
from database import Base, engine
from datetime import datetime
import routers.reports as reports
from database import get_db
import os
from schemas.composition import Composition, CompositionCreate
import crud.composition as crud_composition
from crud.composition_usage_history import use_composition, get_composition_usage_history, revert_composition_usage, get_composition_usage_by_date
from schemas.composition_usage_history import CompositionUsageHistory
from datetime import datetime
from schemas.batch import BatchCreate
from schemas.batch import Batch as BatchSchema
import crud.batch as crud_batch
from datetime import date
import logging
from dateutil import parser
from schemas.daily_batch import DailyBatchCreate, DailyBatchUpdate
import crud.daily_batch as crud_daily_batch
import pandas as pd
from models.batch import Batch as BatchModel
from schemas.app_config import AppConfigCreate, AppConfigUpdate, AppConfigOut
from crud import app_config as crud_app_config
from typing import List, Optional
from models.daily_batch import DailyBatch as DailyBatchModel
import routers.egg_room_reports as egg_room_reports
import routers.bovanswhitelayerperformance as bovanswhitelayerperformance
import routers.batch as batch
import routers.business_partners as business_partners
import routers.purchase_orders as purchase_orders
import routers.payments as payments
import routers.inventory_items as inventory_items
import routers.sales_orders as sales_orders
import routers.sales_payments as sales_payments
from utils.auth_utils import get_current_user, require_group


from fastapi.staticfiles import StaticFiles



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
    "http://localhost:5173,http://127.0.0.1:5173,http://51.21.190.170,https://51.21.190.170,https://poultrix.in"
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
app.include_router(egg_room_reports.router)
app.include_router(bovanswhitelayerperformance.router)

app.include_router(batch.router)
app.include_router(business_partners.router)
app.include_router(purchase_orders.router)
app.include_router(payments.router)
app.include_router(inventory_items.router)
app.include_router(sales_orders.router)
app.include_router(sales_payments.router)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.ico")

@app.get("/")
async def test_route():
    return {"message": "Welcome to the FastAPI application!"}

@app.post("/compositions/", response_model=Composition)
def create_composition(composition: CompositionCreate, db: Session = Depends(get_db), user: dict = Depends(require_group(["admin"]))):
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
def update_composition(composition_id: int, composition: CompositionCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    db_composition = crud_composition.update_composition(db, composition_id, composition)
    if db_composition is None:
        raise HTTPException(status_code=404, detail="Composition not found")
    return db_composition

@app.delete("/compositions/{composition_id}")
def delete_composition(composition_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    success = crud_composition.delete_composition(db, composition_id)
    if not success:
        raise HTTPException(status_code=404, detail="Composition not found")
    return {"message": "Composition deleted"}

@app.post("/compositions/use-composition")
def use_composition_endpoint(
    data: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    composition_id = data["compositionId"]
    shed_no = data["shed_no"]
    times = data["times"]
    used_at = data.get("usedAt")

    if used_at:
        try:
            used_at_dt = datetime.fromisoformat(used_at)
        except ValueError:
            used_at_dt = parser.parse(used_at)
    else:
        used_at_dt = datetime.now()

    # Find the batch_id based on shed_no
    batch = db.query(BatchModel).filter(BatchModel.shed_no == shed_no, BatchModel.is_active == True).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Active batch with shed_no '{shed_no}' not found.")
    batch_id = batch.id

    # Call use_composition and pass changed_by (user from token)
    usage = use_composition(db, composition_id, batch_id, times, used_at_dt, changed_by=user.get('sub'))
    
    # Now, 'usage' object should have its ID populated
    if usage and hasattr(usage, 'id'):
        return {"message": "Composition used and feed quantities updated", "usage_id": usage.id}
    else:
        # This fallback is for unexpected cases, indicating an issue in use_composition
        raise HTTPException(status_code=500, detail="Failed to retrieve usage ID after processing composition.")

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

@app.post("/compositions/revert-usage/{usage_id}")
def revert_composition_usage_endpoint(
    usage_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Reverts a specific composition usage by ID.
    Adds back the quantities to feeds and deletes the usage history record.
    """
    success, message = revert_composition_usage(db, usage_id, changed_by=user.get('sub'))
    if not success:
        raise HTTPException(status_code=404, detail=message)
    return {"message": message}

@app.patch("/compositions/{composition_id}", response_model=Composition)
def patch_composition(composition_id: int, composition: CompositionCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    db_composition = crud_composition.update_composition(db, composition_id, composition)
    if db_composition is None:
        raise HTTPException(status_code=404, detail="Composition not found")
    return db_composition

@app.post("/daily-batch/upload-excel/")
def upload_daily_batch_excel(file: UploadFile = File(...), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """
    Upload and process an Excel file for daily batch data.
    This function processes multiple daily reports within a single Excel file.
    """
    try:
        contents = file.file.read()
        # Read the Excel file, assuming no header row for data extraction
        df = pd.read_excel(io.BytesIO(contents), header=None)

        # Get all valid shed_nos from the batch table for validation
        all_batches = db.query(BatchModel).all()
        valid_shed_nos = {b.shed_no for b in all_batches}

        # Find all rows that contain 'DATE' in the first column
        date_indices = df.index[df[0] == 'DATE'].tolist()
        if not date_indices:
            raise HTTPException(status_code=400, detail="No 'DATE' rows found in the Excel file.")

        processed_records_count = 0

        # Iterate through each identified daily report section
        for i, date_idx in enumerate(date_indices):
            # Extract and parse the report date. Handle multiple date formats.
            report_date_str = df.iloc[date_idx, 1]
            try:
                report_date = pd.to_datetime(report_date_str, format='%m-%d-%Y').date()
            except ValueError:
                try:
                    report_date = pd.to_datetime(report_date_str, format='%d/%m/%Y').date()
                except ValueError:
                    logger.error(f"Could not parse date '{report_date_str}' at row {date_idx}. Skipping this report section.")
                    continue # Skip to the next report section if date parsing fails

            # Data rows for a report start 2 rows after the 'DATE' row
            data_start = date_idx + 2

            # Determine the end of the current report section
            if i + 1 < len(date_indices):
                # If there's a next 'DATE' row, the current section ends just before it.
                data_end = date_indices[i + 1]
            else:
                # This is the last 'DATE' row in the file.
                # Find all 'TOTAL' rows that appear after the start of this data section.
                total_rows_after_start = df.index[(df[0] == 'TOTAL') & (df.index >= data_start)].tolist()
                if total_rows_after_start:
                    # The end of the last section is marked by the *last* 'TOTAL' row.
                    data_end = total_rows_after_start[-1]
                else:
                    # Fallback: if no 'TOTAL' rows are found, process until the end of the DataFrame.
                    data_end = len(df)

            # Process each data row within the identified section
            for row_idx in range(data_start, data_end):
                row = df.iloc[row_idx]

                # Skip rows that are headers or summary rows ('TOTAL', 'GROWER', 'CHICK')
                # as they do not contain valid batch data for individual entries.
                if pd.isna(row[0]) or str(row[0]).strip().upper() in ['TOTAL', 'GROWER', 'CHICK']:
                    continue

                try:
                    # Attempt to convert the first column (BATCH) to an integer.
                    # This will fail for non-numeric rows like 'TOTAL', 'GROWER', 'CHICK'.
                    batch_id_excel = int(row[0])
                except (ValueError, TypeError):
                    logger.warning(f"Skipping row {row_idx} (Date: {report_date}) due to non-integer batch ID: '{row[0]}'.")
                    continue # Skip this row if batch ID is not a valid integer

                # Validate essential data points (BATCH, SHED, AGE, OPENING COUNT)
                if pd.isna(row[1]) or pd.isna(row[2]) or pd.isna(row[3]):
                    logger.warning(f"Skipping row {row_idx} (Date: {report_date}) due to missing essential data: {row.tolist()}")
                    continue

                shed_no_excel = str(row[1]).strip()
                if shed_no_excel not in valid_shed_nos:
                    logger.warning(f"Skipping row {row_idx} (Date: {report_date}) due to shed_no not found in batch table: '{shed_no_excel}'.")
                    continue

                # Retrieve the internal batch_id from your database based on shed_no
                batch_obj = db.query(BatchModel).filter(BatchModel.shed_no == shed_no_excel).first()
                batch_id_for_daily_batch = batch_obj.id if batch_obj else None

                if not batch_id_for_daily_batch:
                    logger.error(f"No internal batch_id found for shed_no '{shed_no_excel}'. Skipping daily_batch row {row_idx}.")
                    continue

                # Safely extract and convert data from Excel row, handling potential NaN values
                age_excel = str(row[2]) if pd.notna(row[2]) else ''
                opening_count_excel = int(row[3]) if pd.notna(row[3]) else 0
                mortality_excel = int(row[4]) if pd.notna(row[4]) else 0
                culls_excel = int(row[5]) if pd.notna(row[5]) else 0
                table_eggs_excel = int(row[7]) if pd.notna(row[7]) else 0
                jumbo_excel = int(row[8]) if pd.notna(row[8]) else 0
                cr_excel = int(row[9]) if pd.notna(row[9]) else 0
                
                # Create an instance of DailyBatchCreate schema
                daily_batch_instance = DailyBatchCreate(
                    batch_id=batch_id_for_daily_batch,
                    shed_no=shed_no_excel,
                    batch_no=f"B-{batch_id_excel:04d}", # Format batch_id_excel with leading zeros
                    upload_date=date.today(),
                    batch_date=report_date,
                    age=age_excel,
                    opening_count=opening_count_excel,
                    mortality=mortality_excel,
                    culls=culls_excel,
                    table_eggs=table_eggs_excel,
                    jumbo=jumbo_excel,
                    cr=cr_excel,
                    # Note: 'closing_count', 'total_eggs_produced', 'hd_percentage'
                    # are typically calculated fields and might not be directly stored
                    # in your DailyBatchCreate schema, depending on your database design.
                )
                # Call your CRUD function to insert the daily batch record
                crud_daily_batch.create_daily_batch(db=db, daily_batch_data=daily_batch_instance)
                processed_records_count += 1

        return {"message": f"File '{file.filename}' processed and {processed_records_count} daily batch records inserted."}

    except HTTPException as he:
        # Re-raise HTTPExceptions as they are already properly formatted
        raise he
    except Exception as e:
        # Catch any other unexpected errors and log them
        logger.exception(f"Unhandled error during Excel upload: {e}")
        # Raise a generic HTTP 500 error for unhandled exceptions
        raise HTTPException(status_code=500, detail=f"Failed to process file: {e}")
    
@app.patch("/daily-batch/{batch_id}/{batch_date}", response_model=DailyBatchUpdate)
def update_daily_batch(
    batch_id: int,
    batch_date: str,
    payload: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
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
def create_config(config: AppConfigCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return crud_app_config.create_config(db, config)


@app.get("/configurations/", response_model=List[AppConfigOut])
def get_configs(name: Optional[str] = None, db: Session = Depends(get_db)):
    configs = crud_app_config.get_config(db, name)
    # Always return a list, even if empty
    return [configs] if name and configs else configs or []

@app.patch("/configurations/{name}/", response_model=AppConfigOut)
def update_config(name: str, config: AppConfigUpdate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
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
    Fetch all daily_batch rows for a given batch_date.
    If a daily_batch row for an active batch does not exist for the given date, it is generated.
    If the batch_date is before a batch's start date, a message is returned for that batch.
    """
    from models.daily_batch import DailyBatch as DailyBatchModel
    from models.batch import Batch as BatchModel
    from utils import calculate_age_progression
    
    today = date.today()
    
    # Get all active batches, ordered by batch_no
    active_batches = db.query(BatchModel).filter(BatchModel.is_active).order_by(BatchModel.batch_no).all()
    
    # Get existing daily batches for the given date and map them by batch_id
    existing_daily_batches = db.query(DailyBatchModel).join(BatchModel).filter(
        DailyBatchModel.batch_date == batch_date, BatchModel.is_active
    ).all()
    existing_daily_batches_map = {db.batch_id: db for db in existing_daily_batches}
    
    result_list = []
    
    for batch in active_batches:
        if batch.id in existing_daily_batches_map:
            # Use existing daily batch
            daily = existing_daily_batches_map[batch.id]
            # Manually construct dict to ensure all fields, including batch_no, are present
            d = {c.name: getattr(daily, c.name) for c in daily.__table__.columns}
            d['closing_count'] = daily.closing_count
            d['hd'] = daily.hd
            d['total_eggs'] = daily.total_eggs
            d['batch_type'] = daily.batch_type
            d['standard_hen_day_percentage'] = daily.standard_hen_day_percentage
            result_list.append(d)
        else:
            # Generate missing daily batch
            if batch_date < batch.date:
                result_list.append({
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
                opening_count = prev_daily.closing_count
                try:
                    prev_age = float(prev_daily.age)
                except (ValueError, TypeError):
                    prev_age = 0.0
                days_diff = (batch_date - prev_daily.batch_date).days
                age = calculate_age_progression(prev_age, days_diff)
            else:
                # This is the first daily record to be generated for this batch.
                # Calculate age based on batch start date.
                opening_count = batch.opening_count
                try:
                    base_age = float(batch.age)
                except (ValueError, TypeError):
                    base_age = 0.0
                days_diff = (batch_date - batch.date).days
                age = calculate_age_progression(base_age, days_diff)

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
            )
            db.add(db_daily)
            db.commit()
            db.refresh(db_daily)
            
            # Manually construct dict to ensure all fields are present
            d = {c.name: getattr(db_daily, c.name) for c in db_daily.__table__.columns}
            d['closing_count'] = db_daily.closing_count
            d['hd'] = db_daily.hd
            d['total_eggs'] = db_daily.total_eggs
            d['batch_type'] = db_daily.batch_type
            d['standard_hen_day_percentage'] = db_daily.standard_hen_day_percentage
            result_list.append(d)
            
    # Sort the final list by 'batch_no' before returning
    result_list.sort(key=lambda x: x.get('batch_no', float('inf')))

    return result_list

@app.get("/compositions/usage-by-date/")
def get_usage_by_date(
    usage_date: date,
    batch_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    return get_composition_usage_by_date(db, usage_date, batch_id)
