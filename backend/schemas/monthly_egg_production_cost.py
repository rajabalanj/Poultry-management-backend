from pydantic import BaseModel, Field, computed_field
from typing import List
from decimal import Decimal
from utils.formatting import format_indian_currency, amount_to_words

class MonthlyEggProductionCost(BaseModel):
    month: str
    total_eggs: int
    total_cost: str = Field(..., description="Total cost formatted to 2 decimal places")
    cost_per_egg: str = Field(..., description="Cost per egg formatted to 2 decimal places")

    # Computed fields for formatted display
    @computed_field
    def total_cost_str(self) -> str:
        return format_indian_currency(Decimal(self.total_cost))

    @computed_field
    def cost_per_egg_str(self) -> str:
        return format_indian_currency(Decimal(self.cost_per_egg))

    @computed_field
    def total_cost_words(self) -> str:
        return amount_to_words(Decimal(self.total_cost))

    @computed_field
    def cost_per_egg_words(self) -> str:
        return amount_to_words(Decimal(self.cost_per_egg))

# Define a type alias for the list of monthly costs
MonthlyEggProductionCostList = List[MonthlyEggProductionCost]
