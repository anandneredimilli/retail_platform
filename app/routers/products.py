from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.core.database import get_db
from app.core.security import get_current_user, CurrentUser
from app.services.product import ProductService
from app.schemas.product import (
    ProductCreate, ProductUpdate, ProductResponse,
    ProductListResponse, StockAdjustRequest
)

router = APIRouter(prefix="/products", tags=["Products"])


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    data: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Create a new product for the current tenant.
    - SKU must be unique within the tenant
    - Also creates an initial entry in product_prices history
    - Requires role: admin or staff
    """
    return await ProductService(db, current_user.tenant_id).create_product(
        data, current_user.user_id
    )


@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search by product name"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    List all products for the current tenant.
    - Supports pagination
    - Filter by category
    - Search by name
    """
    return await ProductService(db, current_user.tenant_id).list_products(
        page, page_size, category, search
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single product by ID."""
    return await ProductService(db, current_user.tenant_id).get_product(product_id)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    data: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Update a product.
    - Only provided fields are updated (partial update)
    - If selling_price changes, a new entry is added to product_prices history
    - Requires role: admin or staff
    """
    return await ProductService(db, current_user.tenant_id).update_product(
        product_id, data, current_user.user_id
    )


@router.post("/{product_id}/adjust-stock", response_model=ProductResponse)
async def adjust_stock(
    product_id: str,
    data: StockAdjustRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Adjust stock quantity for a product.

    Examples:
    - Restock:        { "quantity": 100, "reason": "restock from supplier" }
    - Damaged goods:  { "quantity": -10, "reason": "damaged in warehouse" }
    - Manual fix:     { "quantity": 5,   "reason": "inventory count correction" }

    Uses SELECT FOR UPDATE to prevent race conditions.
    """
    return await ProductService(db, current_user.tenant_id).adjust_stock(
        product_id, data, current_user.user_id
    )


@router.delete("/{product_id}")
async def delete_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Soft delete a product.
    - Product is NOT permanently removed
    - is_deleted = TRUE, deleted_at = NOW()
    - Will no longer appear in listings or be orderable
    - Requires role: admin
    """
    return await ProductService(db, current_user.tenant_id).delete_product(
        product_id, current_user.user_id
    )
