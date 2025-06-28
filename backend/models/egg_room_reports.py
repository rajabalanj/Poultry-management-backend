from sqlalchemy import Column, Date, Integer, DateTime, func
from database import Base

class EggRoomReport(Base):
    __tablename__ = "egg_room_reports"

    report_date = Column(Date, primary_key=True)

    table_opening = Column(Integer)
    table_received = Column(Integer)
    table_transfer = Column(Integer)
    table_damage = Column(Integer)
    table_out = Column(Integer)
    table_closing = Column(Integer)

    grade_c_opening = Column(Integer)
    grade_c_shed_received = Column(Integer)
    grade_c_room_received = Column(Integer)
    grade_c_transfer = Column(Integer)
    grade_c_labour = Column(Integer)
    grade_c_waste = Column(Integer)
    grade_c_closing = Column(Integer)

    jumbo_opening = Column(Integer)
    jumbo_received = Column(Integer)
    jumbo_transfer = Column(Integer)
    jumbo_waste = Column(Integer)
    jumbo_in = Column(Integer)
    jumbo_closing = Column(Integer)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())