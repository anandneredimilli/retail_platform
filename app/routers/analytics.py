from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.mongodb import get_mongo_db
from app.core.security import get_current_user, CurrentUser
from app.services.analytics import AnalyticsService
from app.schemas.analytics import ProfitabilityResponse, DemandTrendResponse, InventoryDepletionResponse
from datetime import datetime
from fastapi import HTTPException

DATE_FORMAT = "%Y-%m-%d"

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/profitability", response_model=ProfitabilityResponse)
async def get_profitability(from_date: str = Query(...), to_date: str = Query(...),
                            db: AsyncSession = Depends(get_db), mongo=Depends(get_mongo_db),
                            current_user: CurrentUser = Depends(get_current_user)):
    try:
        from_date_obj = datetime.strptime(from_date, DATE_FORMAT).date()
        to_date_obj = datetime.strptime(to_date, DATE_FORMAT).date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Expected YYYY-MM-DD"
        )
    return await AnalyticsService(db, mongo, current_user.tenant_id).get_profitability(from_date_obj, to_date_obj)

@router.get("/demand-trend", response_model=DemandTrendResponse)
async def get_demand_trend(db: AsyncSession = Depends(get_db), mongo=Depends(get_mongo_db),
                           current_user: CurrentUser = Depends(get_current_user)):
    return await AnalyticsService(db, mongo, current_user.tenant_id).get_demand_trend()

@router.get("/inventory-depletion", response_model=InventoryDepletionResponse)
async def get_inventory_depletion(db: AsyncSession = Depends(get_db), mongo=Depends(get_mongo_db),
                                  current_user: CurrentUser = Depends(get_current_user)):
    return await AnalyticsService(db, mongo, current_user.tenant_id).get_inventory_depletion()