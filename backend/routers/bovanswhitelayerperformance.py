from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from models.bovanswhitelayerperformance import BovansWhiteLayerPerformance
from database import get_db
from schemas.bovanswhitelayerperformance import BovansPerformanceSchema, PaginatedBovansPerformanceResponse
from utils.tenancy import get_tenant_id

router = APIRouter(
    prefix="/bovans",
    tags=["Bovans Performance"]
)

# Endpoint to get all performance data with pagination
@router.get("/", response_model=PaginatedBovansPerformanceResponse) # <--- IMPORTANT CHANGE HERE
async def get_all_bovans_performance(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Retrieves all performance data for Bovans White Layer chickens with pagination.
    """
    # Get the total count of items first
    total_count = db.query(BovansWhiteLayerPerformance).filter(BovansWhiteLayerPerformance.tenant_id == tenant_id).count()

    # Get the paginated data
    performance_data = db.query(BovansWhiteLayerPerformance).filter(BovansWhiteLayerPerformance.tenant_id == tenant_id).offset(skip).limit(limit).all()

    if not performance_data and total_count > 0:
        # If no data found for the given pagination but total_count is greater than 0,
        # it means the skip/limit parameters are out of range for the available data.
        raise HTTPException(status_code=404, detail="No performance data found for the given pagination parameters")
    elif total_count == 0:
        # If the entire collection is empty, return an empty list and 0 total count.
        return PaginatedBovansPerformanceResponse(data=[], total_count=0)

    # Return the paginated data and the total count
    return PaginatedBovansPerformanceResponse(data=performance_data, total_count=total_count)

# Endpoint to get performance data for a specific age
@router.get("/{age_weeks}", response_model=BovansPerformanceSchema)
async def get_bovans_performance_by_age(age_weeks: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    """
    Retrieves performance data for a specific age (in weeks).
    """
    performance_data = db.query(BovansWhiteLayerPerformance).filter(BovansWhiteLayerPerformance.age_weeks == age_weeks, BovansWhiteLayerPerformance.tenant_id == tenant_id).first()
    if not performance_data:
        raise HTTPException(status_code=404, detail=f"Performance data for age {age_weeks} not found")
    return performance_data