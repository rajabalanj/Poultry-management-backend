from sqlalchemy import Column, Date, Integer, DateTime, func
from sqlalchemy.orm import column_property, synonym
from database import Base

class EggRoomReport(Base):
    __tablename__ = "egg_room_reports"

    report_date = Column(Date, primary_key=True)

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

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Opening balances (actual columns for performance)
    table_opening = Column(Integer, default=0)
    jumbo_opening = Column(Integer, default=0)
    grade_c_opening = Column(Integer, default=0)

    # Closing balances (calculated for single row)
    table_closing = column_property(
        table_opening + table_received - table_transfer - table_damage - table_out + jumbo_out
    )
    jumbo_closing = column_property(
        jumbo_opening + jumbo_received - jumbo_transfer - jumbo_waste + table_out - jumbo_out
    )
    grade_c_closing = column_property(
        grade_c_opening + grade_c_shed_received + table_damage - grade_c_transfer - grade_c_labour - grade_c_waste
    )

    # Synonyms for aliased columns
    table_in = synonym("jumbo_out")
    jumbo_in = synonym("table_out")
    grade_c_room_received = synonym("table_damage")
