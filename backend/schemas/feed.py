from pydantic import BaseModel
from datetime import date
class FeedBase(BaseModel):
    title: str
    quantity: int
    unit: str
    createdDate: date

class Feed(FeedBase):
    pass