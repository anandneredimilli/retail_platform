from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.repositories.base import BaseRepository

class AnalyticsRepository(BaseRepository):

    async def get_profitability(self, from_date: str, to_date: str) -> dict:
        sql = text("""
            SELECT
                COUNT(o.id)                                             AS total_orders,
                COALESCE(SUM(o.total_revenue), 0)                      AS total_revenue,
                COALESCE(SUM(o.total_cost), 0)                         AS total_cost,
                COALESCE(SUM(o.total_profit), 0)                       AS gross_profit,
                CASE WHEN SUM(o.total_revenue) > 0
                     THEN ROUND((SUM(o.total_profit)/SUM(o.total_revenue))*100, 2)
                     ELSE 0 END                                         AS gross_margin_percent,
                CASE WHEN COUNT(o.id) > 0
                     THEN ROUND(SUM(o.total_revenue)/COUNT(o.id), 2)
                     ELSE 0 END                                         AS avg_order_value
            FROM orders o
            WHERE o.tenant_id = :tenant_id AND o.is_deleted = FALSE
              AND o.status = 'confirmed'
              AND o.ordered_at >= :from_date AND o.ordered_at <= :to_date
        """)
        result = await self.db.execute(
            sql, {"tenant_id": self.tenant_id, "from_date": from_date, "to_date": to_date})
        return dict(result.mappings().one())

    async def get_demand_trend(self) -> dict:
        sql = text("""
            WITH current_year AS (
                SELECT DATE(o.ordered_at) AS sale_date,
                       COUNT(DISTINCT o.id) AS order_count,
                       COALESCE(SUM(oi.quantity), 0) AS units_sold,
                       COALESCE(SUM(o.total_revenue), 0) AS revenue
                FROM orders o JOIN order_items oi ON oi.order_id = o.id
                WHERE o.tenant_id = :tenant_id AND o.is_deleted = FALSE
                  AND o.status = 'confirmed'
                  AND EXTRACT(YEAR FROM o.ordered_at) = EXTRACT(YEAR FROM NOW())
                GROUP BY DATE(o.ordered_at)
            ),
            previous_year AS (
                SELECT DATE(o.ordered_at) AS sale_date,
                       COUNT(DISTINCT o.id) AS order_count,
                       COALESCE(SUM(oi.quantity), 0) AS units_sold,
                       COALESCE(SUM(o.total_revenue), 0) AS revenue
                FROM orders o JOIN order_items oi ON oi.order_id = o.id
                WHERE o.tenant_id = :tenant_id AND o.is_deleted = FALSE
                  AND o.status = 'confirmed'
                  AND EXTRACT(YEAR FROM o.ordered_at) = EXTRACT(YEAR FROM NOW()) - 1
                GROUP BY DATE(o.ordered_at)
            )
            SELECT 'current' AS year_type, * FROM current_year
            UNION ALL
            SELECT 'previous' AS year_type, * FROM previous_year
        """)
        result = await self.db.execute(sql, {"tenant_id": self.tenant_id})
        rows = result.mappings().all()
        current, previous = [], []
        for row in rows:
            entry = {"date": str(row["sale_date"]), "order_count": row["order_count"],
                     "units_sold": row["units_sold"], "revenue": float(row["revenue"])}
            (current if row["year_type"] == "current" else previous).append(entry)
        curr_total = sum(r["revenue"] for r in current)
        prev_total = sum(r["revenue"] for r in previous)
        growth = round(((curr_total - prev_total) / prev_total) * 100, 2) if prev_total > 0 else 0.0
        return {"current_year": current, "previous_year": previous, "growth_percent": growth}

    async def get_sales_velocity(self) -> list:
        sql = text("""
            SELECT p.id AS product_id, p.name AS product_name, p.sku,
                   p.stock_quantity AS current_stock,
                   ROUND(COALESCE(SUM(oi.quantity), 0)::numeric / 30, 2) AS avg_daily_sales
            FROM products p
            LEFT JOIN order_items oi ON oi.product_id = p.id
            LEFT JOIN orders o ON o.id = oi.order_id
                AND o.is_deleted = FALSE AND o.status = 'confirmed'
                AND o.ordered_at >= NOW() - INTERVAL '30 days'
            WHERE p.tenant_id = :tenant_id AND p.is_deleted = FALSE AND p.is_active = TRUE
            GROUP BY p.id, p.name, p.sku, p.stock_quantity
        """)
        result = await self.db.execute(sql, {"tenant_id": self.tenant_id})
        return result.mappings().all()