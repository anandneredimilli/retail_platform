from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.repositories.product import ProductRepository
from app.schemas.product import (
    ProductCreate, ProductUpdate, ProductResponse,
    ProductListResponse, StockAdjustRequest
)


class ProductService:
    def __init__(self, db: AsyncSession, tenant_id: str):
        self.repo = ProductRepository(db, tenant_id)

    async def create_product(self, data: ProductCreate, user_id: str) -> ProductResponse:
        product = await self.repo.create(data.model_dump(), user_id)
        return ProductResponse.model_validate(product)

    async def get_product(self, product_id: str) -> ProductResponse:
        product = await self.repo.get_by_id(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return ProductResponse.model_validate(product)

    async def list_products(
        self,
        page: int = 1,
        page_size: int = 20,
        category: str = None,
        search: str = None,
    ) -> ProductListResponse:
        items, total = await self.repo.get_all(page, page_size, category, search)
        return ProductListResponse(
            items=[ProductResponse.model_validate(p) for p in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update_product(
        self, product_id: str, data: ProductUpdate, user_id: str
    ) -> ProductResponse:
        # Only pass fields that were actually provided
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields provided for update")
        product = await self.repo.update(product_id, update_data, user_id)
        return ProductResponse.model_validate(product)

    async def adjust_stock(
        self, product_id: str, data: StockAdjustRequest, user_id: str
    ) -> ProductResponse:
        product = await self.repo.adjust_stock(
            product_id, data.quantity, user_id, data.reason
        )
        return ProductResponse.model_validate(product)

    async def delete_product(self, product_id: str, user_id: str) -> dict:
        await self.repo.soft_delete(product_id, user_id)
        return {"message": "Product deleted successfully", "product_id": product_id}
