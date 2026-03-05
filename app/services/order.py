from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.repositories.order import OrderRepository
from app.schemas.order import OrderCreate, OrderResponse, OrderListResponse

class OrderService:
    def __init__(self, db: AsyncSession, tenant_id: str):
        self.repo = OrderRepository(db, tenant_id)

    async def create_order(self, data: OrderCreate, user_id: str) -> OrderResponse:
        items_data = [{"product_id": i.product_id, "quantity": i.quantity} for i in data.items]
        order = await self.repo.create_order(user_id, data.idempotency_key, items_data)
        order = await self.repo.get_by_id(order.id)
        return OrderResponse.model_validate(order)

    async def get_order(self, order_id: str) -> OrderResponse:
        order = await self.repo.get_by_id(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return OrderResponse.model_validate(order)

    async def list_orders(self, page=1, page_size=20) -> OrderListResponse:
        items, total = await self.repo.get_all(page, page_size)
        return OrderListResponse(
            items=[OrderResponse.model_validate(o) for o in items],
            total=total, page=page, page_size=page_size,
        )