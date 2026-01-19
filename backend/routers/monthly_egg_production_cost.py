from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from typing import List

from database import get_db
from utils.tenancy import get_tenant_id
from crud.daily_batch import get_monthly_egg_production_cost
from schemas.monthly_egg_production_cost import MonthlyEggProductionCost, MonthlyEggProductionCostList

router = APIRouter()

@router.get("/monthly-egg-production-cost", response_model=List[MonthlyEggProductionCost])
def get_monthly_egg_production_cost_endpoint(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Get the cost per egg for each month within a given date range.
    This includes both feed costs and operational expenses.
    """
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Start date must be before end date")

    monthly_costs = get_monthly_egg_production_cost(
        db=db,
        start_date=start_date,
        end_date=end_date,
        tenant_id=tenant_id
    )

    return monthly_costs
