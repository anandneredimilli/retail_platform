from pydantic import BaseModel
from typing import List
from decimal import Decimal
from datetime import datetime

class OrderItemCreate(BaseModel):
    product_id: str
    quantity: int

class OrderCreate(BaseModel):
    idempotency_key: str
    items: List[OrderItemCreate]

class OrderItemResponse(BaseModel):
    id: str
    product_id: str
    quantity: int
    unit_price: Decimal
    unit_cost: Decimal
    line_revenue: Decimal
    line_cost: Decimal
    line_profit: Decimal
    class Config:
        from_attributes = True

class OrderResponse(BaseModel):
    id: str
    tenant_id: str
    idempotency_key: str
    status: str
    total_revenue: Decimal
    total_cost: Decimal
    total_profit: Decimal
    ordered_at: datetime
    items: List[OrderItemResponse]
    class Config:
        from_attributes = True

class OrderListResponse(BaseModel):
    items: list[OrderResponse]
    total: int
    page: int
    page_size: int