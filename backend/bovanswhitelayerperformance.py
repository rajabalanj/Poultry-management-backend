from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from models.bovanswhitelayerperformance import BovansWhiteLayerPerformance
from database import get_db
from schemas.bovanswhitelayerperformance import BovansPerformanceSchema


router = APIRouter(
    prefix="/bovans",
    tags=["Bovans Performance"]
)

# Endpoint to get all performance data with pagination
@router.get("/", response_model=List[BovansPerformanceSchema])
async def get_all_bovans_performance(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100), # Default to 10 items per page
    db: Session = Depends(get_db)
):
    """
    Retrieves all performance data for Bovans White Layer chickens with pagination.
    """
    performance_data = db.query(BovansWhiteLayerPerformance).offset(skip).limit(limit).all()
    if not performance_data:
        # It's better to return an empty list for no data on a paginated endpoint
        # rather than a 404, unless the entire collection is truly empty.
        # For now, keeping the 404 for consistency with existing code, but
        # consider returning an empty list and total count for front-end pagination.
        raise HTTPException(status_code=404, detail="No performance data found for the given pagination parameters")
    return performance_data

# Endpoint to get performance data for a specific age
@router.get("/{age_weeks}", response_model=BovansPerformanceSchema)
async def get_bovans_performance_by_age(age_weeks: int, db: Session = Depends(get_db)):
    """
    Retrieves performance data for a specific age (in weeks).
    """
    performance_data = db.query(BovansWhiteLayerPerformance).filter(BovansWhiteLayerPerformance.age_weeks == age_weeks).first()
    if not performance_data:
        raise HTTPException(status_code=404, detail=f"Performance data for age {age_weeks} not found")
    return performance_data