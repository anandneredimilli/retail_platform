from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.mongodb import get_mongo_db
from app.core.security import get_current_user, CurrentUser
from app.services.inventory import InventoryService

router = APIRouter(prefix="/inventory", tags=["Inventory"])

@router.post("/snapshot")
async def take_snapshot(snapshot_date: str = Query(None),
                        db: AsyncSession = Depends(get_db),
                        mongo=Depends(get_mongo_db),
                        current_user: CurrentUser = Depends(get_current_user)):
    return await InventoryService(db, mongo, current_user.tenant_id).take_snapshot(snapshot_date)