from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from app.models.postgres import Product, ProductPrice
from app.repositories.base import BaseRepository
from fastapi import HTTPException
from app.utils.json_utils import normalize_json


class ProductRepository(BaseRepository):

    async def create(self, data: dict, user_id: str) -> Product:
        # Check SKU uniqueness within tenant
        existing = await self.db.execute(
            select(Product).where(
                Product.tenant_id == self.tenant_id,
                Product.sku == data["sku"],
                Product.is_deleted == False,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"SKU '{data['sku']}' already exists")

        product = Product(tenant_id=self.tenant_id, **data)
        self.db.add(product)
        await self.db.flush()

        # Insert initial price into product_prices history
        price = ProductPrice(
            tenant_id=self.tenant_id,
            product_id=product.id,
            selling_price=data["selling_price"],
            effective_from=datetime.utcnow(),
            effective_to=None,
        )
        self.db.add(price)

        await self.log_audit(
            action="CREATE",
            entity="product",
            entity_id=product.id,
            user_id=user_id,
            old_data=None,
            new_data=normalize_json(data),
        )
        return product

    async def get_by_id(self, product_id: str) -> Product | None:
        result = await self.db.execute(
            select(Product).where(
                Product.id == product_id,
                Product.tenant_id == self.tenant_id,
                Product.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_sku(self, sku: str) -> Product | None:
        result = await self.db.execute(
            select(Product).where(
                Product.sku == sku,
                Product.tenant_id == self.tenant_id,
                Product.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def get_all(self, page: int = 1, page_size: int = 20,
                      category: str = None, search: str = None):
        query = select(Product).where(
            Product.tenant_id == self.tenant_id,
            Product.is_deleted == False,
        )

        # Optional filters
        if category:
            query = query.where(Product.category == category)
        if search:
            query = query.where(Product.name.ilike(f"%{search}%"))

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar()

        # Paginate
        offset = (page - 1) * page_size
        query = query.order_by(Product.created_at.desc()).offset(offset).limit(page_size)
        result = await self.db.execute(query)
        items = result.scalars().all()

        return items, total

    async def update(self, product_id: str, data: dict, user_id: str) -> Product:
        product = await self.get_by_id(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        old_data = {
            "name": product.name,
            "category": product.category,
            "unit_cost": str(product.unit_cost),
            "selling_price": str(product.selling_price),
            "stock_quantity": product.stock_quantity,
            "reorder_level": product.reorder_level,
        }

        # Check if selling_price changed — if so, update product_prices history
        new_selling_price = data.get("selling_price")
        if new_selling_price and float(new_selling_price) != float(product.selling_price):
            # Close current active price
            await self.db.execute(
                select(ProductPrice).where(
                    ProductPrice.product_id == product_id,
                    ProductPrice.effective_to == None,
                )
            )
            result = await self.db.execute(
                select(ProductPrice).where(
                    ProductPrice.product_id == product_id,
                    ProductPrice.effective_to == None,
                )
            )
            active_price = result.scalar_one_or_none()
            if active_price:
                active_price.effective_to = datetime.utcnow()

            # Insert new price record
            new_price = ProductPrice(
                tenant_id=self.tenant_id,
                product_id=product_id,
                selling_price=new_selling_price,
                effective_from=datetime.utcnow(),
                effective_to=None,
            )
            self.db.add(new_price)

        # Apply updates
        for key, value in data.items():
            if value is not None:
                setattr(product, key, value)
        product.updated_at = datetime.utcnow()

        await self.log_audit(
            action="UPDATE",
            entity="product",
            entity_id=product_id,
            user_id=user_id,
            old_data=old_data,
            new_data={k: str(v) for k, v in data.items() if v is not None},
        )
        return product

    async def adjust_stock(self, product_id: str, quantity: int,
                           user_id: str, reason: str = None) -> Product:
        # Use SELECT FOR UPDATE to prevent race conditions
        result = await self.db.execute(
            select(Product).where(
                Product.id == product_id,
                Product.tenant_id == self.tenant_id,
                Product.is_deleted == False,
            ).with_for_update()
        )
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        new_stock = product.stock_quantity + quantity
        if new_stock < 0:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock. Current: {product.stock_quantity}, Requested reduction: {abs(quantity)}"
            )

        old_stock = product.stock_quantity
        product.stock_quantity = new_stock
        product.updated_at = datetime.utcnow()

        await self.log_audit(
            action="UPDATE",
            entity="product",
            entity_id=product_id,
            user_id=user_id,
            old_data={"stock_quantity": old_stock},
            new_data={"stock_quantity": new_stock, "adjustment": quantity, "reason": reason},
        )
        return product

    async def soft_delete(self, product_id: str, user_id: str) -> bool:
        product = await self.get_by_id(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        product.is_deleted = True
        product.deleted_at = datetime.utcnow()
        product.updated_at = datetime.utcnow()

        await self.log_audit(
            action="DELETE",
            entity="product",
            entity_id=product_id,
            user_id=user_id,
            old_data={"is_deleted": False},
            new_data={"is_deleted": True},
        )
        return True
