from pydantic import BaseModel

class FeedInCompositionBase(BaseModel):
    feed_id: int
    weight: float

class FeedInCompositionCreate(FeedInCompositionBase):
    pass

class FeedInComposition(FeedInCompositionBase):
    id: int
    class Config:
        form_attributes = True