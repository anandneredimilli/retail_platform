from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.models.postgres import Order, OrderItem, Product
from app.repositories.base import BaseRepository
from fastapi import HTTPException

class OrderRepository(BaseRepository):

    async def get_by_idempotency_key(self, key: str) -> Order | None:
        result = await self.db.execute(
            select(Order).where(Order.tenant_id == self.tenant_id,
                Order.idempotency_key == key, Order.is_deleted == False))
        return result.scalar_one_or_none()

    async def create_order(self, user_id: str, idempotency_key: str, items_data: list) -> Order:
        existing = await self.get_by_idempotency_key(idempotency_key)
        if existing:
            return existing  # Idempotent: return existing order

        total_revenue, total_cost, order_items = 0, 0, []

        for item in items_data:
            # SELECT FOR UPDATE prevents race conditions on stock
            result = await self.db.execute(
                select(Product).where(
                    Product.id == item["product_id"],
                    Product.tenant_id == self.tenant_id,
                    Product.is_deleted == False,
                ).with_for_update()
            )
            product = result.scalar_one_or_none()
            if not product:
                raise HTTPException(status_code=404, detail=f"Product {item['product_id']} not found")
            if product.stock_quantity < item["quantity"]:
                raise HTTPException(status_code=400,
                    detail=f"Insufficient stock for {product.name}. Available: {product.stock_quantity}")

            line_revenue = float(product.selling_price) * item["quantity"]
            line_cost    = float(product.unit_cost) * item["quantity"]
            total_revenue += line_revenue
            total_cost    += line_cost
            product.stock_quantity -= item["quantity"]  # Deduct stock in same transaction

            order_items.append({
                "product": product, "quantity": item["quantity"],
                "unit_price": product.selling_price, "unit_cost": product.unit_cost,
                "line_revenue": line_revenue, "line_cost": line_cost,
                "line_profit": line_revenue - line_cost,
            })

        order = Order(tenant_id=self.tenant_id, user_id=user_id,
                      idempotency_key=idempotency_key, total_revenue=total_revenue,
                      total_cost=total_cost, total_profit=total_revenue - total_cost)
        self.db.add(order)
        await self.db.flush()

        for d in order_items:
            self.db.add(OrderItem(
                tenant_id=self.tenant_id, order_id=order.id, product_id=d["product"].id,
                quantity=d["quantity"], unit_price=d["unit_price"], unit_cost=d["unit_cost"],
                line_revenue=d["line_revenue"], line_cost=d["line_cost"], line_profit=d["line_profit"],
            ))

        await self.log_audit("CREATE", "order", order.id, user_id,
                             None, {"idempotency_key": idempotency_key})
        await self.db.flush()
        return order

    async def get_by_id(self, order_id: str) -> Order | None:
        result = await self.db.execute(
            select(Order).options(selectinload(Order.items)).where(
                Order.id == order_id, Order.tenant_id == self.tenant_id, Order.is_deleted == False))
        return result.scalar_one_or_none()

    async def get_all(self, page=1, page_size=20):
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(Order).options(selectinload(Order.items)).where(
                Order.tenant_id == self.tenant_id, Order.is_deleted == False
            ).order_by(Order.ordered_at.desc()).offset(offset).limit(page_size))
        items = result.scalars().all()
        count = await self.db.execute(
            select(func.count(Order.id)).where(
                Order.tenant_id == self.tenant_id, Order.is_deleted == False))
        return items, count.scalar()