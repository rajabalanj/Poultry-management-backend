from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models.bovanswhitelayerperformance import BovansWhiteLayerPerformance
from database import get_db
from schemas.bovanswhitelayerperformance import BovansPerformanceSchema


router = APIRouter(
    prefix="/bovans",
    tags=["Bovans Performance"]
)

# Endpoint to get all performance data
@router.get("/", response_model=List[BovansPerformanceSchema])
async def get_all_bovans_performance(db: Session = Depends(get_db)):
    """
    Retrieves all performance data for Bovans White Layer chickens.
    """
    # Query all records from the BovansWhiteLayerPerformance table
    performance_data = db.query(BovansWhiteLayerPerformance).all()
    if not performance_data:
        raise HTTPException(status_code=404, detail="No performance data found")
    return performance_data

# Endpoint to get performance data for a specific age
@router.get("/{age_weeks}", response_model=BovansPerformanceSchema)
async def get_bovans_performance_by_age(age_weeks: int, db: Session = Depends(get_db)):
    """
    Retrieves performance data for a specific age (in weeks).
    """
    # Query a single record by age_weeks
    performance_data = db.query(BovansWhiteLayerPerformance).filter(BovansWhiteLayerPerformance.age_weeks == age_weeks).first()
    if not performance_data:
        raise HTTPException(status_code=404, detail=f"Performance data for age {age_weeks} not found")
    return performance_data