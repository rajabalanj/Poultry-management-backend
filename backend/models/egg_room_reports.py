# File: models/egg_room_reports.py

from sqlalchemy import Column, Date, Integer, DateTime, func
from models.app_config import AppConfig
from database import Base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from datetime import datetime # Import datetime for date conversion
# import pdb

class EggRoomReport(Base):
    __tablename__ = "egg_room_reports"

    report_date = Column(Date, primary_key=True)

    table_received = Column(Integer)
    table_transfer = Column(Integer)
    table_damage = Column(Integer)
    table_out = Column(Integer)

    grade_c_shed_received = Column(Integer)
    grade_c_room_received = Column(Integer)
    grade_c_transfer = Column(Integer)
    grade_c_labour = Column(Integer)
    grade_c_waste = Column(Integer)

    jumbo_received = Column(Integer)
    jumbo_transfer = Column(Integer)
    jumbo_waste = Column(Integer)
    jumbo_in = Column(Integer)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Ensure the __init__ method is removed if it's still present in your file.
    # def __init__(self, db: Session):
    #     self.db = db

    @hybrid_property
    def table_opening(self):
        session = inspect(self).session
        if not session:
            return None # Object is detached from a session

        egg_opening_date_config = session.query(AppConfig).filter(AppConfig.name == 'egg_opening_date').first()
        egg_opening_date_value = egg_opening_date_config.value if egg_opening_date_config else None

        if egg_opening_date_value:
            try:
                # Convert the string date to a datetime.date object for comparison
                egg_opening_date_value = datetime.strptime(egg_opening_date_value, "%Y-%m-%d").date()
            except ValueError:
                # Handle cases where the string might not be a valid date format
                egg_opening_date_value = None

        # If an opening date is configured and the current report date is before it, return 0
        if egg_opening_date_value and self.report_date < egg_opening_date_value:
            return 0

        # Try to get the closing balance from the previous day's report
        previous_report = session.query(EggRoomReport).filter(EggRoomReport.report_date < self.report_date).order_by(EggRoomReport.report_date.desc()).first()
        if previous_report:
            # Recursively call table_closing on the previous report
            return previous_report.table_closing
        else:
            # If no previous report, get the initial opening balance from app_config
            app_config_table_opening = session.query(AppConfig).filter(AppConfig.name == 'table_opening').first()
            return int(app_config_table_opening.value) if app_config_table_opening and app_config_table_opening.value is not None else 0

    @hybrid_property
    def jumbo_opening(self):
        session = inspect(self).session
        if not session:
            return None

        egg_opening_date_config = session.query(AppConfig).filter(AppConfig.name == 'egg_opening_date').first()
        egg_opening_date_value = egg_opening_date_config.value if egg_opening_date_config else None

        if egg_opening_date_value:
            try:
                egg_opening_date_value = datetime.strptime(egg_opening_date_value, "%Y-%m-%d").date()
            except ValueError:
                egg_opening_date_value = None

        if egg_opening_date_value and self.report_date < egg_opening_date_value:
            return 0

        previous_report = session.query(EggRoomReport).filter(EggRoomReport.report_date < self.report_date).order_by(EggRoomReport.report_date.desc()).first()
        if previous_report:
            return previous_report.jumbo_closing
        else:
            app_config_jumbo_opening = session.query(AppConfig).filter(AppConfig.name == 'jumbo_opening').first()
            return int(app_config_jumbo_opening.value) if app_config_jumbo_opening and app_config_jumbo_opening.value is not None else 0

    @hybrid_property
    def grade_c_opening(self):
        session = inspect(self).session
        if not session:
            return None

        egg_opening_date_config = session.query(AppConfig).filter(AppConfig.name == 'egg_opening_date').first()
        egg_opening_date_value = egg_opening_date_config.value if egg_opening_date_config else None

        if egg_opening_date_value:
            try:
                egg_opening_date_value = datetime.strptime(egg_opening_date_value, "%Y-%m-%d").date()
            except ValueError:
                egg_opening_date_value = None

        if egg_opening_date_value and self.report_date < egg_opening_date_value:
            return 0

        previous_report = session.query(EggRoomReport).filter(EggRoomReport.report_date < self.report_date).order_by(EggRoomReport.report_date.desc()).first()
        if previous_report:
            return previous_report.grade_c_closing
        else:
            app_config_grade_c_opening = session.query(AppConfig).filter(AppConfig.name == 'grade_c_opening').first()
            return int(app_config_grade_c_opening.value) if app_config_grade_c_opening and app_config_grade_c_opening.value is not None else 0

    @hybrid_property
    def table_closing(self):
        table_opening = self.table_opening if self.table_opening is not None else 0
        table_received = self.table_received if self.table_received is not None else 0
        table_transfer = self.table_transfer if self.table_transfer is not None else 0
        table_damage = self.table_damage if self.table_damage is not None else 0
        table_out = self.table_out if self.table_out is not None else 0
        return table_opening + table_received - table_transfer - table_damage - table_out

    @hybrid_property
    def jumbo_closing(self):
        jumbo_opening = self.jumbo_opening if self.jumbo_opening is not None else 0
        jumbo_received = self.jumbo_received if self.jumbo_received is not None else 0
        jumbo_transfer = self.jumbo_transfer if self.jumbo_transfer is not None else 0
        jumbo_waste = self.jumbo_waste if self.jumbo_waste is not None else 0
        jumbo_in = self.jumbo_in if self.jumbo_in is not None else 0
        return jumbo_opening + jumbo_received - jumbo_transfer - jumbo_waste + jumbo_in

    @hybrid_property
    def grade_c_closing(self):
        grade_c_opening = self.grade_c_opening if self.grade_c_opening is not None else 0
        grade_c_shed_received = self.grade_c_shed_received if self.grade_c_shed_received is not None else 0
        grade_c_room_received = self.grade_c_room_received if self.grade_c_room_received is not None else 0
        grade_c_transfer = self.grade_c_transfer if self.grade_c_transfer is not None else 0
        grade_c_labour = self.grade_c_labour if self.grade_c_labour is not None else 0
        grade_c_waste = self.grade_c_waste if self.grade_c_waste is not None else 0
        return grade_c_opening + grade_c_shed_received + grade_c_room_received - grade_c_transfer - grade_c_labour - grade_c_waste