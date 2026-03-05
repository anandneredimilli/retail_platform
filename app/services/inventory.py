from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.postgres import Product
from pymongo import UpdateOne

class InventoryService:
    def __init__(self, db, mongo, tenant_id: str):
        self.db = db
        self.mongo = mongo
        self.tenant_id = tenant_id

    async def take_snapshot(self, snapshot_date: str = None) -> dict:
        if not snapshot_date:
            snapshot_date = datetime.utcnow().strftime("%Y-%m-%d")
        result = await self.db.execute(
            select(Product).where(Product.tenant_id == self.tenant_id,
                Product.is_deleted == False, Product.is_active == True))
        products = result.scalars().all()
        operations = []

        for p in products:
            snapshot = {
                "tenant_id": self.tenant_id,
                "product_id": p.id,
                "product_name": p.name,
                "sku": p.sku,
                "category": p.category,
                "quantity_on_hand": p.stock_quantity,
                "reorder_level": p.reorder_level,
                "snapshot_date": snapshot_date,
                "created_at": datetime.utcnow(),
            }

            operations.append(
                UpdateOne(
                    {
                        "tenant_id": self.tenant_id,
                        "product_id": p.id,
                        "snapshot_date": snapshot_date
                    },
                    {"$set": snapshot},
                    upsert=True
                )
            )

        if operations:
            await self.mongo.inventory_snapshots.bulk_write(operations)
        return {"message": "Snapshot saved", "products_count": len(products), "date": snapshot_date}