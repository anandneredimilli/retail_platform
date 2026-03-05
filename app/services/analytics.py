from sqlalchemy import Date
from datetime import datetime
from app.repositories.analytics import AnalyticsRepository
from app.schemas.analytics import (ProfitabilityResponse, DemandTrendResponse,
    InventoryDepletionResponse, InventoryDepletionItem)

class AnalyticsService:
    def __init__(self, db, mongo, tenant_id: str):
        self.db = db
        self.mongo = mongo
        self.tenant_id = tenant_id
        self.repo = AnalyticsRepository(db, tenant_id)

    async def get_profitability(self, from_date: Date, to_date: Date) -> ProfitabilityResponse:
        from_date_str = from_date.strftime("%Y-%m-%d")
        to_date_str = to_date.strftime("%Y-%m-%d")
        # Check cache first
        cache = await self.mongo.kpi_cache.find_one({
            "tenant_id": self.tenant_id, "kpi_type": "profitability",
            "period": f"{from_date_str}_{to_date_str}",
        })
        if cache:
            return ProfitabilityResponse(**cache["data"], from_date=from_date_str, to_date=to_date_str)


        data = await self.repo.get_profitability(from_date, to_date)
        response = ProfitabilityResponse(
            from_date=from_date_str, to_date=to_date_str,
            total_revenue=data["total_revenue"], total_cost=data["total_cost"],
            gross_profit=data["gross_profit"],
            gross_margin_percent=float(data["gross_margin_percent"]),
            total_orders=int(data["total_orders"]), avg_order_value=data["avg_order_value"],
        )
        # Save to cache
        await self.mongo.kpi_cache.update_one(
            {"tenant_id": self.tenant_id, "kpi_type": "profitability", "period": f"{from_date_str}_{to_date_str}"},
            {"$set": {"tenant_id": self.tenant_id, "kpi_type": "profitability",
                      "period": f"{from_date_str}_{to_date_str}", "computed_at": datetime.utcnow(),
                      "expires_at": datetime.utcnow().replace(hour=23, minute=59),
                      "data": response.model_dump(exclude={"from_date", "to_date"})}},
            upsert=True,
        )
        return response

    async def get_demand_trend(self) -> DemandTrendResponse:
        return DemandTrendResponse(**(await self.repo.get_demand_trend()))

    async def get_inventory_depletion(self) -> InventoryDepletionResponse:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        velocity_rows = await self.repo.get_sales_velocity()
        items = []
        for row in velocity_rows:
            avg_daily = float(row["avg_daily_sales"])
            current_stock = int(row["current_stock"])
            days = round(current_stock / avg_daily, 1) if avg_daily > 0 else None
            status = ("critical" if days and days <= 7 else
                      "low" if days and days <= 30 else "healthy")
            items.append(InventoryDepletionItem(
                product_id=str(row["product_id"]), product_name=row["product_name"],
                sku=row["sku"], current_stock=current_stock, avg_daily_sales=avg_daily,
                estimated_days_to_stockout=days, status=status,
            ))
        return InventoryDepletionResponse(items=items, snapshot_date=today)