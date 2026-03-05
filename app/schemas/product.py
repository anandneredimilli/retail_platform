from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from datetime import datetime


class ProductCreate(BaseModel):
    name: str
    sku: str
    category: Optional[str] = None
    unit_cost: Decimal
    selling_price: Decimal
    stock_quantity: int = 0
    reorder_level: int = 10


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    unit_cost: Optional[Decimal] = None
    selling_price: Optional[Decimal] = None
    stock_quantity: Optional[int] = None
    reorder_level: Optional[int] = None


class StockAdjustRequest(BaseModel):
    quantity: int          # positive = add stock, negative = reduce stock
    reason: Optional[str] = None  # e.g. "restock", "damaged goods", "manual correction"


class ProductResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    sku: str
    category: Optional[str]
    unit_cost: Decimal
    selling_price: Decimal
    stock_quantity: int
    reorder_level: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    items: List[ProductResponse]
    total: int
    page: int
    page_size: int
