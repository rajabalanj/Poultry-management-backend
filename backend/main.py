from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from database import Base, engine
from datetime import datetime
import routers.reports as reports
import os
import routers.bovanswhitelayerperformance as bovanswhitelayerperformance
import routers.batch as batch
import routers.business_partners as business_partners
import routers.purchase_orders as purchase_orders
import routers.payments as payments
import routers.inventory_items as inventory_items
import routers.sales_orders as sales_orders
import routers.sales_payments as sales_payments
import routers.financial_reports as financial_reports
import routers.operational_expenses as operational_expenses
import routers.composition_usage_history as composition_usage_history
import routers.daily_batch as daily_batch
import routers.app_config as app_config
import routers.composition as composition
import routers.egg_room_reports as egg_room_reports
import logging
from fastapi.openapi.utils import get_openapi


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

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Poultry Management API",
        version="1.0.0",
        description="API for Poultry Management System",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    # Apply security globally to all endpoints
    openapi_schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi


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
app.include_router(financial_reports.router)
app.include_router(operational_expenses.router)
app.include_router(composition_usage_history.router)
app.include_router(app_config.router)
app.include_router(composition.router)
app.include_router(daily_batch.router)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.ico")

@app.get("/")
async def test_route():
    return {"message": "Welcome to the FastAPI application!"}


