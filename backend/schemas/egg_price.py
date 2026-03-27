
"""
Pydantic schemas for egg price data.
"""
from datetime import datetime, date
from pydantic import BaseModel


class EggPriceBase(BaseModel):
    """Base schema for egg price data."""
    single_egg_rate: str | None = None
    dozen_eggs_rate: str | None = None
    hundred_eggs_rate: str | None = None
    average_market_price: str | None = None
    best_market_price: str | None = None
    lowest_market_price: str | None = None
    best_price_market: str | None = None
    lowest_price_market: str | None = None


class EggPriceCreate(EggPriceBase):
    """Schema for creating a new egg price record."""
    price_date: date


class EggPriceUpdate(EggPriceBase):
    """Schema for updating an existing egg price record."""
    pass


class EggPrice(EggPriceBase):
    """Schema for egg price data as returned from the API."""
    id: str
    price_date: date
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
