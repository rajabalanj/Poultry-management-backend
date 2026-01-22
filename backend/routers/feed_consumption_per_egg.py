from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from typing import List

from database import get_db
from utils.tenancy import get_tenant_id
from crud.daily_batch import get_feed_consumption_per_egg
from schemas.feed_consumption_per_egg import FeedConsumptionPerEgg, FeedConsumptionPerEggList

router = APIRouter()

@router.get("/feed-consumption-per-egg", response_model=List[FeedConsumptionPerEgg])
def get_feed_consumption_per_egg_endpoint(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Get the feed consumption (in grams) required to produce one egg
    for each month within a given date range.
    """
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Start date must be before end date")

    monthly_feed_consumption = get_feed_consumption_per_egg(
        db=db,
        start_date=start_date,
        end_date=end_date,
        tenant_id=tenant_id
    )

    return monthly_feed_consumption
