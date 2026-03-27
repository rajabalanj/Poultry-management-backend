
"""
CRUD operations for egg price data.
"""
import logging
from datetime import date, datetime
from typing import Optional
from sqlalchemy.orm import Session
from models.egg_price import EggPrice as EggPriceModel
from schemas.egg_price import EggPriceCreate, EggPriceUpdate

logger = logging.getLogger(__name__)


def get_egg_price_by_date(db: Session, price_date: date) -> Optional[EggPriceModel]:
    """
    Get egg price data for a specific date.

    Args:
        db: Database session
        price_date: Date to fetch price for

    Returns:
        EggPriceModel if found, None otherwise
    """
    return db.query(EggPriceModel).filter(EggPriceModel.price_date == price_date).first()


def get_latest_egg_price(db: Session) -> Optional[EggPriceModel]:
    """
    Get the latest egg price data.

    Args:
        db: Database session

    Returns:
        EggPriceModel if found, None otherwise
    """
    return db.query(EggPriceModel).order_by(EggPriceModel.price_date.desc()).first()


def create_egg_price(db: Session, egg_price: EggPriceCreate) -> EggPriceModel:
    """
    Create a new egg price record.

    Args:
        db: Database session
        egg_price: Egg price data to create

    Returns:
        Created EggPriceModel
    """
    # Generate ID from date
    egg_price_id = f"egg_price_{egg_price.price_date.strftime('%Y%m%d')}"

    db_egg_price = EggPriceModel(
        id=egg_price_id,
        price_date=egg_price.price_date,
        single_egg_rate=egg_price.single_egg_rate,
        dozen_eggs_rate=egg_price.dozen_eggs_rate,
        hundred_eggs_rate=egg_price.hundred_eggs_rate,
        average_market_price=egg_price.average_market_price,
        best_market_price=egg_price.best_market_price,
        lowest_market_price=egg_price.lowest_market_price,
        best_price_market=egg_price.best_price_market,
        lowest_price_market=egg_price.lowest_price_market,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    db.add(db_egg_price)
    db.commit()
    db.refresh(db_egg_price)
    logger.info(f"Created new egg price record for {egg_price.price_date}")
    return db_egg_price


def update_egg_price(db: Session, egg_price_id: str, egg_price: EggPriceUpdate) -> Optional[EggPriceModel]:
    """
    Update an existing egg price record.

    Args:
        db: Database session
        egg_price_id: ID of the egg price to update
        egg_price: Updated egg price data

    Returns:
        Updated EggPriceModel if found, None otherwise
    """
    db_egg_price = db.query(EggPriceModel).filter(EggPriceModel.id == egg_price_id).first()

    if not db_egg_price:
        return None

    # Update fields if provided
    if egg_price.single_egg_rate is not None:
        db_egg_price.single_egg_rate = egg_price.single_egg_rate
    if egg_price.dozen_eggs_rate is not None:
        db_egg_price.dozen_eggs_rate = egg_price.dozen_eggs_rate
    if egg_price.hundred_eggs_rate is not None:
        db_egg_price.hundred_eggs_rate = egg_price.hundred_eggs_rate
    if egg_price.average_market_price is not None:
        db_egg_price.average_market_price = egg_price.average_market_price
    if egg_price.best_market_price is not None:
        db_egg_price.best_market_price = egg_price.best_market_price
    if egg_price.lowest_market_price is not None:
        db_egg_price.lowest_market_price = egg_price.lowest_market_price
    if egg_price.best_price_market is not None:
        db_egg_price.best_price_market = egg_price.best_price_market
    if egg_price.lowest_price_market is not None:
        db_egg_price.lowest_price_market = egg_price.lowest_price_market

    db_egg_price.updated_at = datetime.now()
    db.commit()
    db.refresh(db_egg_price)
    logger.info(f"Updated egg price record {egg_price_id}")
    return db_egg_price
