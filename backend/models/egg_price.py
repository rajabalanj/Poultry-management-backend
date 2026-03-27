
"""
Database model for storing daily egg price information.
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Date
from database import Base


class EggPrice(Base):
    """
    Model for storing daily egg price information.

    Attributes:
        id: Primary key
        price_date: Date of the price
        single_egg_rate: Price of a single egg
        dozen_eggs_rate: Price of a dozen eggs
        hundred_eggs_rate: Price of 100 eggs
        average_market_price: Average market price
        best_market_price: Best market price
        lowest_market_price: Lowest market price
        best_price_market: Market with best price
        lowest_price_market: Market with lowest price
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """
    __tablename__ = "egg_prices"

    id = Column(String, primary_key=True, index=True)
    price_date = Column(Date, unique=True, index=True, nullable=False)
    single_egg_rate = Column(String)
    dozen_eggs_rate = Column(String)
    hundred_eggs_rate = Column(String)
    average_market_price = Column(String)
    best_market_price = Column(String)
    lowest_market_price = Column(String)
    best_price_market = Column(String)
    lowest_price_market = Column(String)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
