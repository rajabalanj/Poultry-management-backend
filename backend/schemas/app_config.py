from pydantic import BaseModel
from typing import Optional
from enum import Enum

class AppConfigKey(str, Enum):
    LOW_KG_THRESHOLD = "lowKgThreshold"
    LOW_TON_THRESHOLD = "lowTonThreshold"
    MEDICINE_LOW_KG_THRESHOLD = "medicineLowKgThreshold"
    MEDICINE_LOW_GRAM_THRESHOLD = "medicineLowGramThreshold"
    HEN_DAY_DEVIATION = "henDayDeviation"
    EGG_STOCK_TOLERANCE = "EGG_STOCK_TOLERANCE"
    TABLE_OPENING = "table_opening"
    JUMBO_OPENING = "jumbo_opening"
    GRADE_C_OPENING = "grade_c_opening"
    SYSTEM_START_DATE = "system_start_date"
    GENERAL_LEDGER_OPENING_BALANCE = "general_ledger_opening_balance"
    PERFORMANCE_STANDARD_SOURCE = "performance_standard_source"
    SELLER_ADDRESS = "seller_address"
    EGG_OPENING_DATE = "egg_opening_date"
    FEED_ACCURACY = "FeedAccuracy"

class AppConfigBase(BaseModel):
    name: AppConfigKey
    value: str
    tenant_id: Optional[str] = None

class AppConfigCreate(AppConfigBase):
    pass

class AppConfigUpdate(BaseModel):
    value: Optional[str] = None

class AppConfigOut(AppConfigBase):
    id: int
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    class Config:
        from_attributes = True

class FinancialConfig(BaseModel):
    general_ledger_opening_balance: Optional[float] = None