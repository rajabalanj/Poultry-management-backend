
"""
Router for egg price endpoints.
"""
import logging
from datetime import date
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from schemas.egg_price import EggPrice, EggPriceCreate
from crud.egg_price import get_egg_price_by_date, get_latest_egg_price, create_egg_price
from tasks.egg_price_tasks import fetch_egg_price_from_kisandeals, update_daily_egg_price
from utils.auth_utils import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/egg-prices",
    tags=["Egg Prices"],
    dependencies=[Depends(get_current_user)]
)


@router.get("/latest", response_model=EggPrice)
def get_latest_price(
    db: Session = Depends(get_db)
):
    """
    Get the latest egg price data.

    Returns:
        EggPrice: Latest egg price information
    """
    latest_price = get_latest_egg_price(db)
    if not latest_price:
        raise HTTPException(status_code=404, detail="No egg price data found")
    return latest_price


@router.get("/date/{price_date}", response_model=EggPrice)
def get_price_by_date(
    price_date: date,
    db: Session = Depends(get_db)
):
    """
    Get egg price data for a specific date.

    Args:
        price_date: Date to fetch price for

    Returns:
        EggPrice: Egg price information for the specified date
    """
    price = get_egg_price_by_date(db, price_date)
    if not price:
        raise HTTPException(status_code=404, detail=f"No egg price data found for {price_date}")
    return price


@router.post("/refresh")
def refresh_egg_price(
    db: Session = Depends(get_db)
):
    """
    Manually trigger a refresh of egg price data from the source website.
    This will fetch the latest data and update the database.

    Returns:
        Dict: Status of the refresh operation
    """
    result = update_daily_egg_price()
    if result:
        return {"status": "success", "message": "Egg price data refreshed successfully", "data": result}
    else:
        raise HTTPException(status_code=500, detail="Failed to refresh egg price data")


@router.get("/fetch-current")
def fetch_current_price(
    db: Session = Depends(get_db)
):
    """
    Fetch current egg price from the source website.
    First checks if today's data is already in the database.
    If not, fetches from the source website and stores it.

    Returns:
        Dict: Current egg price information
    """
    today = date.today()
    
    # Check if today's price data exists in the database
    existing_price = get_egg_price_by_date(db, today)
    
    if existing_price:
        # Return data from database
        return {
            "source": "database",
            "date": existing_price.price_date.strftime("%Y-%m-%d"),
            "Single Egg Rate": existing_price.single_egg_rate,
            "Dozen Eggs Rate": existing_price.dozen_eggs_rate,
            "100 Eggs Rate": existing_price.hundred_eggs_rate,
            "Average Market Price": existing_price.average_market_price,
            "Best Market Price": existing_price.best_market_price,
            "Lowest Market Price": existing_price.lowest_market_price,
            "Best Price Market": existing_price.best_price_market,
            "Lowest Price Market": existing_price.lowest_price_market
        }
    
    # If not in database, fetch from external source
    price_data = fetch_egg_price_from_kisandeals()
    if not price_data:
        raise HTTPException(status_code=500, detail="Failed to fetch egg price data")
    
    # Store the fetched data in the database
    from schemas.egg_price import EggPriceCreate
    egg_price_create = EggPriceCreate(
        price_date=today,
        single_egg_rate=price_data.get("Single Egg Rate"),
        dozen_eggs_rate=price_data.get("Dozen Eggs Rate"),
        hundred_eggs_rate=price_data.get("100 Eggs Rate"),
        average_market_price=price_data.get("Average Market Price"),
        best_market_price=price_data.get("Best Market Price"),
        lowest_market_price=price_data.get("Lowest Market Price"),
        best_price_market=price_data.get("Best Price Market"),
        lowest_price_market=price_data.get("Lowest Price Market")
    )
    create_egg_price(db, egg_price_create)
    
    # Add source information to the response
    price_data["source"] = "external_api"
    price_data["date"] = today.strftime("%Y-%m-%d")
    
    return price_data
