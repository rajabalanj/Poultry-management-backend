from sqlalchemy import Column, Date, Integer, DateTime, func
# from models.app_config import AppConfig # REMOVE THIS IMPORT
from database import Base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from datetime import datetime, timedelta # Import timedelta for date arithmetic

class EggRoomReport(Base):
    __tablename__ = "egg_room_reports"

    report_date = Column(Date, primary_key=True)

    table_received = Column(Integer)
    table_transfer = Column(Integer)
    table_damage = Column(Integer)
    table_out = Column(Integer)

    grade_c_shed_received = Column(Integer)
    # grade_c_room_received = Column(Integer)
    grade_c_transfer = Column(Integer)
    grade_c_labour = Column(Integer)
    grade_c_waste = Column(Integer)

    jumbo_received = Column(Integer)
    jumbo_transfer = Column(Integer)
    jumbo_waste = Column(Integer)
    # jumbo_in = Column(Integer)
    jumbo_out = Column(Integer)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    @hybrid_property
    def table_opening(self):
        session = inspect(self).session
        if not session:
            return None # Object is detached from a session

        # Calculate the previous day's date
        previous_day = self.report_date - timedelta(days=1)

        # Try to get the closing balance from the previous day's report
        previous_report = session.query(EggRoomReport).filter(
            EggRoomReport.report_date == previous_day
        ).first()

        if previous_report:
            # If a previous report exists, its table_closing is today's table_opening
            return previous_report.table_closing
        else:
            # If no previous report, this is the first entry, so opening is 0
            # Or, if you need a specific initial value, you'd insert the first report
            # with that value directly in the database.
            return 0

    @hybrid_property
    def jumbo_opening(self):
        session = inspect(self).session
        if not session:
            return None

        previous_day = self.report_date - timedelta(days=1)
        previous_report = session.query(EggRoomReport).filter(
            EggRoomReport.report_date == previous_day
        ).first()

        if previous_report:
            return previous_report.jumbo_closing
        else:
            return 0

    @hybrid_property
    def grade_c_opening(self):
        session = inspect(self).session
        if not session:
            return None

        previous_day = self.report_date - timedelta(days=1)
        previous_report = session.query(EggRoomReport).filter(
            EggRoomReport.report_date == previous_day
        ).first()

        if previous_report:
            return previous_report.grade_c_closing
        else:
            return 0

    @hybrid_property
    def table_closing(self):
        # Ensure all components are treated as integers, defaulting to 0 if None
        table_opening = self.table_opening if self.table_opening is not None else 0
        table_received = self.table_received if self.table_received is not None else 0
        table_transfer = self.table_transfer if self.table_transfer is not None else 0
        table_damage = self.table_damage if self.table_damage is not None else 0
        table_out = self.table_out if self.table_out is not None else 0
        table_in = self.table_in if self.table_in is not None else 0
        return table_opening + table_received - table_transfer - table_damage - table_out + table_in

    @hybrid_property
    def jumbo_closing(self):
        jumbo_opening = self.jumbo_opening if self.jumbo_opening is not None else 0
        jumbo_received = self.jumbo_received if self.jumbo_received is not None else 0
        jumbo_transfer = self.jumbo_transfer if self.jumbo_transfer is not None else 0
        jumbo_waste = self.jumbo_waste if self.jumbo_waste is not None else 0
        jumbo_in = self.jumbo_in if self.jumbo_in is not None else 0
        jumbo_out = self.jumbo_out if self.jumbo_out is not None else 0
        return jumbo_opening + jumbo_received - jumbo_transfer - jumbo_waste + jumbo_in - jumbo_out

    @hybrid_property
    def grade_c_closing(self):
        grade_c_opening = self.grade_c_opening if self.grade_c_opening is not None else 0
        grade_c_shed_received = self.grade_c_shed_received if self.grade_c_shed_received is not None else 0
        grade_c_room_received = self.grade_c_room_received if self.grade_c_room_received is not None else 0
        grade_c_transfer = self.grade_c_transfer if self.grade_c_transfer is not None else 0
        grade_c_labour = self.grade_c_labour if self.grade_c_labour is not None else 0
        grade_c_waste = self.grade_c_waste if self.grade_c_waste is not None else 0
        return grade_c_opening + grade_c_shed_received + grade_c_room_received - grade_c_transfer - grade_c_labour - grade_c_waste
    
    @hybrid_property
    def jumbo_in(self):
        return self.table_out if self.table_out is not None else 0
    
    @hybrid_property
    def table_in(self):
        return self.jumbo_out if self.jumbo_out is not None else 0
    
    @hybrid_property
    def grade_c_room_received(self):
        return self.table_damage if self.table_damage is not None else 0