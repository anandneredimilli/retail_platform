from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.postgres import Tenant

class TenantRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, name: str, slug: str) -> Tenant:
        tenant = Tenant(name=name, slug=slug)
        self.db.add(tenant)
        await self.db.flush()
        return tenant

    async def get_by_slug(self, slug: str) -> Tenant | None:
        result = await self.db.execute(
            select(Tenant).where(Tenant.slug == slug, Tenant.is_deleted == False))
        return result.scalar_one_or_none()