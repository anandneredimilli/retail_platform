import asyncio
from datetime import datetime, timedelta
from app.background.celery_app import celery_app
from app.core.config import settings

def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

@celery_app.task(name="app.background.tasks.aggregate_daily_sales")
def aggregate_daily_sales():
    async def _run():
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy import text
        from motor.motor_asyncio import AsyncIOMotorClient
        engine    = create_async_engine(settings.DATABASE_URL)
        Session   = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        mongo     = AsyncIOMotorClient(settings.MONGODB_URL)[settings.MONGO_DB]
        yesterday_start = (datetime.utcnow() - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        yesterday_end = (datetime.utcnow() - timedelta(days=1)).replace(
            hour=23, minute=59, second=59, microsecond=999999
        )
        yesterday_label = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        async with Session() as db:
            result = await db.execute(text("SELECT DISTINCT tenant_id FROM orders WHERE is_deleted = FALSE"))
            for row in result.fetchall():
                tenant_id = str(row[0])
                res = await db.execute(text("""
                    SELECT COUNT(DISTINCT o.id) AS total_orders,
                           COALESCE(SUM(o.total_revenue),0) AS total_revenue,
                           COALESCE(SUM(o.total_cost),0) AS total_cost,
                           COALESCE(SUM(o.total_profit),0) AS total_profit,
                           CASE WHEN SUM(o.total_revenue)>0
                                THEN ROUND((SUM(o.total_profit)/SUM(o.total_revenue))*100,2)
                                ELSE 0 END AS gross_margin_percent
                    FROM orders o
                    WHERE o.tenant_id=:t AND o.is_deleted=FALSE
                      AND o.status='confirmed' 
                      AND o.ordered_at >= :from_dt
                      AND o.ordered_at <= :to_dt
                """), {
                        "t": tenant_id,
                        "from_dt":   yesterday_start,
                        "to_dt":     yesterday_end,
                    })
                r = res.mappings().one()
                await mongo.daily_sales_summary.update_one(
                    {"tenant_id": tenant_id, "date": yesterday_label},
                    {"$set": {"tenant_id": tenant_id, "date": yesterday_label,
                              "total_orders": r["total_orders"],
                              "total_revenue": float(r["total_revenue"]),
                              "total_cost": float(r["total_cost"]),
                              "total_profit": float(r["total_profit"]),
                              "gross_margin_percent": float(r["gross_margin_percent"]),
                              "updated_at": datetime.utcnow()}},
                    upsert=True,
                )
        await engine.dispose()
    run_async(_run())

@celery_app.task(name="app.background.tasks.take_daily_inventory_snapshot")
def take_daily_inventory_snapshot():
    async def _run():
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy import select
        from motor.motor_asyncio import AsyncIOMotorClient
        from app.models.postgres import Product
        engine  = create_async_engine(settings.DATABASE_URL)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        mongo   = AsyncIOMotorClient(settings.MONGODB_URL)[settings.MONGO_DB]
        today   = datetime.utcnow().strftime("%Y-%m-%d")
        async with Session() as db:
            result = await db.execute(select(Product).where(
                Product.is_deleted == False, Product.is_active == True))
            for p in result.scalars().all():
                await mongo.inventory_snapshots.update_one(
                    {"tenant_id": str(p.tenant_id), "product_id": str(p.id), "snapshot_date": today},
                    {"$set": {"tenant_id": str(p.tenant_id), "product_id": str(p.id),
                              "product_name": p.name, "sku": p.sku, "category": p.category,
                              "quantity_on_hand": p.stock_quantity, "reorder_level": p.reorder_level,
                              "snapshot_date": today, "created_at": datetime.utcnow()}},
                    upsert=True,
                )
        await engine.dispose()
    run_async(_run())

@celery_app.task(name="app.background.tasks.compute_kpi_cache")
def compute_kpi_cache():
    async def _run():
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        from sqlalchemy import text
        from motor.motor_asyncio import AsyncIOMotorClient
        engine   = create_async_engine(settings.DATABASE_URL)
        Session  = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        mongo    = AsyncIOMotorClient(settings.MONGODB_URL)[settings.MONGO_DB]
        now      = datetime.utcnow()
        from_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        to_date   = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        period    = now.strftime("%Y-%m")
        async with Session() as db:
            result = await db.execute(text("SELECT DISTINCT tenant_id FROM orders WHERE is_deleted=FALSE"))
            for row in result.fetchall():
                tenant_id = str(row[0])
                res = await db.execute(text("""
                    SELECT COUNT(o.id) AS total_orders,
                           COALESCE(SUM(o.total_revenue),0) AS total_revenue,
                           COALESCE(SUM(o.total_cost),0) AS total_cost,
                           COALESCE(SUM(o.total_profit),0) AS gross_profit,
                           CASE WHEN SUM(o.total_revenue)>0
                                THEN ROUND((SUM(o.total_profit)/SUM(o.total_revenue))*100,2)
                                ELSE 0 END AS gross_margin_percent,
                           CASE WHEN COUNT(o.id)>0
                                THEN ROUND(SUM(o.total_revenue)/COUNT(o.id),2)
                                ELSE 0 END AS avg_order_value
                    FROM orders o WHERE o.tenant_id=:t AND o.is_deleted=FALSE
                      AND o.status='confirmed'
                      AND o.ordered_at>=:f AND o.ordered_at<=:d
                """), {"t": tenant_id, "f": from_date, "d": to_date})
                r = res.mappings().one()
                await mongo.kpi_cache.update_one(
                    {"tenant_id": tenant_id, "kpi_type": "profitability", "period": period},
                    {"$set": {"tenant_id": tenant_id, "kpi_type": "profitability",
                              "period": period, "computed_at": now,
                              "expires_at": now + timedelta(hours=1),
                              "data": {k: float(v) for k, v in r.items()}}},
                    upsert=True,
                )
        await engine.dispose()
    run_async(_run())