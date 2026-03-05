from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal

class ProfitabilityResponse(BaseModel):
    model_config = {
        "json_encoders": {Decimal: float}
    }
    
    from_date: str
    to_date: str
    total_revenue: Decimal
    total_cost: Decimal
    gross_profit: Decimal
    gross_margin_percent: Decimal
    total_orders: int
    avg_order_value: Decimal

class DailyDemand(BaseModel):
    date: str
    units_sold: int
    revenue: Decimal
    order_count: int

class DemandTrendResponse(BaseModel):
    current_year: List[DailyDemand]
    previous_year: List[DailyDemand]
    growth_percent: float

class InventoryDepletionItem(BaseModel):
    product_id: str
    product_name: str
    sku: str
    current_stock: int
    avg_daily_sales: float
    estimated_days_to_stockout: Optional[float]
    status: str  # critical / low / healthy

class InventoryDepletionResponse(BaseModel):
    items: List[InventoryDepletionItem]
    snapshot_date: str