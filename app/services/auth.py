from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.repositories.tenant import TenantRepository
from app.repositories.user import UserRepository
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from app.schemas.auth import TenantRegisterRequest, LoginRequest, TokenResponse

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.tenant_repo = TenantRepository(db)
        self.user_repo   = UserRepository(db)

    async def register(self, data: TenantRegisterRequest) -> TokenResponse:
        if await self.tenant_repo.get_by_slug(data.tenant_slug):
            raise HTTPException(status_code=400, detail="Tenant slug already exists")
        tenant = await self.tenant_repo.create(data.tenant_name, data.tenant_slug)
        user   = await self.user_repo.create(tenant.id, data.email, data.password, data.role)
        return self._make_tokens(user, tenant.id)

    async def login(self, data: LoginRequest, tenant_slug: str) -> TokenResponse:
        tenant = await self.tenant_repo.get_by_slug(tenant_slug)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        user = await self.user_repo.get_by_email(tenant.id, data.email)
        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return self._make_tokens(user, tenant.id)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return TokenResponse(
            access_token=create_access_token(payload),
            refresh_token=create_refresh_token(payload),
        )

    def _make_tokens(self, user, tenant_id) -> TokenResponse:
        data = {"user_id": user.id, "tenant_id": tenant_id, "role": user.role, "email": user.email}
        return TokenResponse(access_token=create_access_token(data), refresh_token=create_refresh_token(data))