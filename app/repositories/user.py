from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.postgres import User
from app.core.security import hash_password

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, tenant_id, email, password, role="staff") -> User:
        user = User(tenant_id=tenant_id, email=email,
                    password_hash=hash_password(password), role=role)
        self.db.add(user)

        await self.db.flush()
        return user

    async def get_by_email(self, tenant_id, email) -> User | None:
        result = await self.db.execute(
            select(User).where(User.tenant_id == tenant_id, User.email == email,
                               User.is_deleted == False, User.is_active == True))
        return result.scalar_one_or_none()