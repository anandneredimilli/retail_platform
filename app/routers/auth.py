from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.auth import AuthService
from app.schemas.auth import TenantRegisterRequest, LoginRequest, TokenResponse, RefreshRequest

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: TenantRegisterRequest, db: AsyncSession = Depends(get_db)):
    return await AuthService(db).register(data)

@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest,
                tenant_slug: str = Query(..., description="Your tenant slug e.g. nike-store"),
                db: AsyncSession = Depends(get_db)):
    return await AuthService(db).login(data, tenant_slug)

@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await AuthService(db).refresh(data.refresh_token)