from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func, case, cast, Float
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
from sqlalchemy.ext.hybrid import hybrid_property
from models.bovanswhitelayerperformance import BovansWhiteLayerPerformance
from sqlalchemy.orm import object_session
from models.composition_usage_history import CompositionUsageHistory
from models.inventory_items import InventoryItem
from decimal import Decimal
from models.audit_mixin import TimestampMixin
import pytz


class DailyBatch(Base, TimestampMixin):
    __tablename__ = "daily_batch"
    batch_id = Column(Integer, ForeignKey("batch.id"), primary_key=True)
    tenant_id = Column(String, index=True)
    batch = relationship("Batch", back_populates="daily_batches")
    shed_no = Column(String)
    batch_no = Column(String)
    upload_date = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.timezone('Asia/Kolkata')).date())
    batch_date = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.timezone('Asia/Kolkata')).date(), primary_key=True)
    age = Column(String)
    opening_count = Column(Integer)
    mortality = Column(Integer, default=0)
    culls = Column(Integer, default=0)
    table_eggs = Column(Integer, default=0)
    jumbo = Column(Integer, default=0)
    cr = Column(Integer, default=0)
    notes = Column(String, nullable=True)

    @hybrid_property
    def total_eggs(self):
        return self.table_eggs + self.jumbo + self.cr

    @total_eggs.expression
    def total_eggs(cls):
        return func.coalesce(cls.table_eggs, 0) + func.coalesce(cls.jumbo, 0) + func.coalesce(cls.cr, 0)

    @hybrid_property
    def closing_count(self):
        return self.opening_count - (self.mortality + self.culls)

    @closing_count.expression
    def closing_count(cls):
        return func.coalesce(cls.opening_count, 0) - (func.coalesce(cls.mortality, 0) + func.coalesce(cls.culls, 0))

    @hybrid_property
    def hd(self):
        if self.closing_count and self.closing_count > 0:
            return self.total_eggs / self.closing_count
        return 0

    @hd.expression
    def hd(cls):
        return case(
            (cls.closing_count > 0, cls.total_eggs / cls.closing_count),
            else_=0
        )
    
    @hybrid_property
    def standard_hen_day_percentage(self):
        session = object_session(self)
        bovans_performance = session.query(BovansWhiteLayerPerformance).filter(
            BovansWhiteLayerPerformance.age_weeks == int(float(self.age)) + 1
        ).first()
        return bovans_performance.lay_percent if bovans_performance else None

    @standard_hen_day_percentage.expression
    def standard_hen_day_percentage(cls):
        # Create a subquery to get the lay_percent based on age
        from sqlalchemy import select, Integer
        subquery = select(BovansWhiteLayerPerformance.lay_percent).where(
            BovansWhiteLayerPerformance.age_weeks == cast(cls.age, Integer) + 1
        ).limit(1).label('lay_percent')
        return subquery
    
    @hybrid_property
    def standard_feed_in_grams(self):
        session = object_session(self)
        bovans_performance = session.query(BovansWhiteLayerPerformance).filter(
            BovansWhiteLayerPerformance.age_weeks == int(float(self.age)) + 1
        ).first()
        # This will return the standard feed per bird. 
        # You might need to multiply this by closing_count in the frontend 
        # or in another property to get the total standard feed for the flock.
        return bovans_performance.feed_intake_per_day_g if bovans_performance else None

    @standard_feed_in_grams.expression
    def standard_feed_in_grams(cls):
        # Create a subquery to get the feed_intake_per_day_g based on age
        from sqlalchemy import select
        subquery = select(BovansWhiteLayerPerformance.feed_intake_per_day_g).where(
            BovansWhiteLayerPerformance.age_weeks == cast(cls.age, Integer) + 1
        ).limit(1).label('feed_intake_per_day_g')
        return subquery

    @hybrid_property
    def standard_feed_in_kg(self):
        if self.standard_feed_in_grams:
            return self.standard_feed_in_grams / 1000
        return None

    @standard_feed_in_kg.expression
    def standard_feed_in_kg(cls):
        return cls.standard_feed_in_grams / 1000

    @hybrid_property
    def batch_type(self):
        if float(self.age) < 16:
            return 'Chick'
        elif float(self.age) <= 18:  # include 18 in this range
            return 'Grower'
        elif float(self.age) > 18:
            return 'Layer'
        
    @batch_type.expression
    def batch_type(cls):
        return case(
            (cast(cls.age, Float) < 16, 'Chick'),
            (cast(cls.age, Float) <= 18, 'Grower'),
            else_='Layer'
        )
        
    @hybrid_property
    def feed_in_grams(self):
        session = object_session(self)
        if not session:
            return 0

        total_feed_kg = Decimal(0)
        
        usages = session.query(CompositionUsageHistory).filter(
            CompositionUsageHistory.batch_id == self.batch_id,
            func.date(CompositionUsageHistory.used_at) == self.batch_date
        ).all()

        for usage in usages:
            for item_in_comp in usage.composition_items:
                item = session.query(InventoryItem).filter(InventoryItem.id == item_in_comp['inventory_item_id']).first()
                if item and item.category == 'Feed':
                    total_feed_kg += Decimal(str(item_in_comp['weight'])) * Decimal(usage.times)

        return float(total_feed_kg * 1000)

    @feed_in_grams.expression
    def feed_in_grams(cls):
        from sqlalchemy import select, func, cast, Date, JSON, Float, Integer
        from sqlalchemy.dialects.postgresql import JSONB
        from models.composition_usage_history import CompositionUsageHistory
        from models.inventory_items import InventoryItem

        # This is a complex subquery that calculates the total feed in grams for a daily batch.
        # It is specific to PostgreSQL as it uses JSONB functions.
        
        # 1. Unnest the composition_items array of objects
        composition_items_cte = select(
            CompositionUsageHistory.id.label("usage_id"),
            (func.jsonb_array_elements(CompositionUsageHistory.composition_items)).label("item_data")
        ).where(
            CompositionUsageHistory.batch_id == cls.batch_id,
            cast(CompositionUsageHistory.used_at, Date) == cast(cls.batch_date, Date)
        ).cte("composition_items_cte")

        # 2. Join with InventoryItem to filter by category 'Feed'
        # and calculate the weight for each item
        feed_items_cte = select(
            composition_items_cte.c.usage_id,
            (cast(composition_items_cte.c.item_data['weight'], Float) *
             select(CompositionUsageHistory.times).where(CompositionUsageHistory.id == composition_items_cte.c.usage_id).scalar_subquery()).label("total_weight_kg")
        ).select_from(composition_items_cte).join(
            InventoryItem,
            cast(composition_items_cte.c.item_data['inventory_item_id'], Integer) == InventoryItem.id
        ).where(
            InventoryItem.category == 'Feed'
        ).cte("feed_items_cte")

        # 3. Sum the weights and convert to grams
        total_feed_kg_subquery = select(
            func.sum(feed_items_cte.c.total_weight_kg)
        ).select_from(feed_items_cte).scalar_subquery()

        return func.coalesce(total_feed_kg_subquery * 1000, 0)

    @hybrid_property
    def feed_in_kg(self):
        return self.feed_in_grams / 1000 if self.feed_in_grams is not None else 0
    
    @feed_in_kg.expression
    def feed_in_kg(cls):
        return cls.feed_in_grams / 1000