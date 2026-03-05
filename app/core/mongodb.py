from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

mongo_client: AsyncIOMotorClient = None

async def connect_mongo():
    global mongo_client
    mongo_client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = mongo_client[settings.MONGO_DB]
    await db.inventory_snapshots.create_index(
        [("tenant_id", 1), ("product_id", 1), ("snapshot_date", -1)], unique=True)
    await db.daily_sales_summary.create_index(
        [("tenant_id", 1), ("date", -1)], unique=True)
    await db.kpi_cache.create_index(
        [("tenant_id", 1), ("kpi_type", 1), ("period", 1)], unique=True)
    await db.kpi_cache.create_index([("expires_at", 1)], expireAfterSeconds=0)

async def disconnect_mongo():
    global mongo_client
    if mongo_client:
        mongo_client.close()

def get_mongo_db() -> AsyncIOMotorDatabase:
    return mongo_client[settings.MONGO_DB]