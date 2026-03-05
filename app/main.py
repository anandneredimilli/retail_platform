from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import engine, Base
from app.core.mongodb import connect_mongo, disconnect_mongo
from app.routers import auth, orders, inventory, analytics, products

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await connect_mongo()
    yield
    await engine.dispose()
    await disconnect_mongo()

app = FastAPI(title=settings.APP_NAME,
              description="Multi-Tenant Retail Analytics Platform",
              version="1.0.0", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(orders.router)
app.include_router(inventory.router)
app.include_router(analytics.router)
app.include_router(products.router)

@app.get("/health")
async def health():
    return {"status": "healthy", "app": settings.APP_NAME}