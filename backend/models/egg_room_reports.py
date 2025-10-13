from sqlalchemy import Column, Date, Integer, func, String
from sqlalchemy.orm import column_property, synonym
from database import Base
from models.audit_mixin import AuditMixin

class EggRoomReport(Base, AuditMixin):
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

    # Closing balances (calculated for single row)
    table_closing = column_property(
        func.coalesce(table_opening, 0) + func.coalesce(table_received, 0) - func.coalesce(table_transfer, 0) - func.coalesce(table_damage, 0) - func.coalesce(table_out, 0) + func.coalesce(jumbo_out, 0)
    )
    jumbo_closing = column_property(
        func.coalesce(jumbo_opening, 0) + func.coalesce(jumbo_received, 0) - func.coalesce(jumbo_transfer, 0) - func.coalesce(jumbo_waste, 0) + func.coalesce(table_out, 0) - func.coalesce(jumbo_out, 0)
    )
    grade_c_closing = column_property(
        func.coalesce(grade_c_opening, 0) + func.coalesce(grade_c_shed_received, 0) + func.coalesce(table_damage, 0) - func.coalesce(grade_c_transfer, 0) - func.coalesce(grade_c_labour, 0) - func.coalesce(grade_c_waste, 0)
    )

    # Synonyms for aliased columns
    table_in = synonym("jumbo_out")
    jumbo_in = synonym("table_out")
    grade_c_room_received = synonym("table_damage")
