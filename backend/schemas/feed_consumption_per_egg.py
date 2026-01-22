from pydantic import BaseModel, Field
from typing import List

class FeedConsumptionPerEgg(BaseModel):
    month: str
    total_eggs: int
    total_feed_grams: float
    total_feed_kg: float
    feed_per_egg_grams: float
    feed_per_egg_kg: float

# Define a type alias for the list of monthly feed consumption
FeedConsumptionPerEggList = List[FeedConsumptionPerEgg]
