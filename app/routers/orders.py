from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user, CurrentUser
from app.services.order import OrderService
from app.schemas.order import OrderCreate, OrderResponse, OrderListResponse

router = APIRouter(prefix="/orders", tags=["Orders"])

@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(data: OrderCreate, db: AsyncSession = Depends(get_db),
                       current_user: CurrentUser = Depends(get_current_user)):
    return await OrderService(db, current_user.tenant_id).create_order(data, current_user.user_id)

@router.get("", response_model=OrderListResponse)
async def list_orders(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                      db: AsyncSession = Depends(get_db),
                      current_user: CurrentUser = Depends(get_current_user)):
    return await OrderService(db, current_user.tenant_id).list_orders(page, page_size)

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str, db: AsyncSession = Depends(get_db),
                    current_user: CurrentUser = Depends(get_current_user)):
    return await OrderService(db, current_user.tenant_id).get_order(order_id)