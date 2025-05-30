from pydantic import BaseModel
from typing import List
from .feed_in_composition import FeedInComposition, FeedInCompositionCreate

class CompositionBase(BaseModel):
    name: str

class CompositionCreate(CompositionBase):
    feeds: List[FeedInCompositionCreate]

class Composition(CompositionBase):
    id: int
    feeds: List[FeedInComposition]
    class Config:
        form_attributes = True