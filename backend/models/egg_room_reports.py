from sqlalchemy import Column, Date, Integer, func, String
from sqlalchemy.orm import synonym
from sqlalchemy.ext.hybrid import hybrid_property
from database import Base
from models.audit_mixin import TimestampMixin

class EggRoomReport(Base, TimestampMixin):
    __tablename__ = "egg_room_reports"

    report_date = Column(Date, primary_key=True)
    tenant_id = Column(String, primary_key=True, index=True)

    # User-entered data
    table_received = Column(Integer, default=0)
    table_transfer = Column(Integer, default=0)
    table_damage = Column(Integer, default=0)
    table_out = Column(Integer, default=0)

    grade_c_shed_received = Column(Integer, default=0)
    grade_c_transfer = Column(Integer, default=0)
    grade_c_labour = Column(Integer, default=0)
    grade_c_waste = Column(Integer, default=0)

    jumbo_received = Column(Integer, default=0)
    jumbo_transfer = Column(Integer, default=0)
    jumbo_waste = Column(Integer, default=0)
    jumbo_out = Column(Integer, default=0)

    # Opening balances (actual columns for performance)
    table_opening = Column(Integer, default=0)
    jumbo_opening = Column(Integer, default=0)
    grade_c_opening = Column(Integer, default=0)

    @hybrid_property
    def table_closing(self):
        return (self.table_opening or 0) + (self.table_received or 0) - (self.table_transfer or 0) - (self.table_damage or 0) - (self.table_out or 0) + (self.jumbo_out or 0)

    @table_closing.expression
    def table_closing(cls):
        return func.coalesce(cls.table_opening, 0) + func.coalesce(cls.table_received, 0) - func.coalesce(cls.table_transfer, 0) - func.coalesce(cls.table_damage, 0) - func.coalesce(cls.table_out, 0) + func.coalesce(cls.jumbo_out, 0)

    @hybrid_property
    def jumbo_closing(self):
        return (self.jumbo_opening or 0) + (self.jumbo_received or 0) - (self.jumbo_transfer or 0) - (self.jumbo_waste or 0) + (self.table_out or 0) - (self.jumbo_out or 0)

    @jumbo_closing.expression
    def jumbo_closing(cls):
        return func.coalesce(cls.jumbo_opening, 0) + func.coalesce(cls.jumbo_received, 0) - func.coalesce(cls.jumbo_transfer, 0) - func.coalesce(cls.jumbo_waste, 0) + func.coalesce(cls.table_out, 0) - func.coalesce(cls.jumbo_out, 0)

    @hybrid_property
    def grade_c_closing(self):
        return (self.grade_c_opening or 0) + (self.grade_c_shed_received or 0) + (self.table_damage or 0) - (self.grade_c_transfer or 0) - (self.grade_c_labour or 0) - (self.grade_c_waste or 0)
    
    @grade_c_closing.expression
    def grade_c_closing(cls):
        return func.coalesce(cls.grade_c_opening, 0) + func.coalesce(cls.grade_c_shed_received, 0) + func.coalesce(cls.table_damage, 0) - func.coalesce(cls.grade_c_transfer, 0) - func.coalesce(cls.grade_c_labour, 0) - func.coalesce(cls.grade_c_waste, 0)

    # Synonyms for aliased columns
    table_in = synonym("jumbo_out")
    jumbo_in = synonym("table_out")
    grade_c_room_received = synonym("table_damage")
