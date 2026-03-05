# Multi-Tenant Retail Analytics Platform

## Table of Contents
1. [Architecture Explanation](#architecture-explanation)
2. [Database Schema Diagram](#database-schema-diagram)
3. [Index Strategy](#index-strategy)
4. [Query Optimization Explanation](#query-optimization-explanation)
5. [Why MongoDB Instead of PostgreSQL](#why-mongodb-instead-of-postgresql)
6. [Background Processing](#background-processing)
7. [Setup Instructions](#setup-instructions)
8. [API Documentation](#api-documentation)

---

## Architecture Explanation

### Overview
This platform is built using **Clean Layered Architecture** where each layer has a single responsibility and communicates only with the layer directly below it.

```
┌─────────────────────────────────────────────────────┐
│                   CLIENT / POSTMAN                  │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP Request
                      ▼
┌─────────────────────────────────────────────────────┐
│                 ROUTERS (FastAPI)                   │
│   auth.py  orders.py  products.py  analytics.py     │
│   - Accepts HTTP requests                           │
│   - Validates JWT token                             │
│   - Passes data to Service layer                    │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│                   SERVICES                          │
│  auth.py  order.py  product.py  analytics.py        │
│   - Contains all business logic                     │
│   - Orchestrates repositories                       │
│   - No direct DB access                             │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│                 REPOSITORIES                        │
│  tenant  user  product  order  analytics            │
│   - All database queries live here                  │
│   - tenant_id enforced on EVERY query               │
│   - Audit logging on every write                    │
└──────────┬──────────────────────────┬───────────────┘
           │                          │
           ▼                          ▼
┌──────────────────┐       ┌──────────────────────────┐
│   PostgreSQL     │       │        MongoDB            │
│  (Transactional) │       │  (Analytics & Snapshots)  │
│                  │       │                           │
│  - tenants       │       │  - inventory_snapshots    │
│  - users         │       │  - daily_sales_summary    │
│  - products      │       │  - kpi_cache              │
│  - orders        │       │                           │
│  - order_items   │       └──────────────────────────┘
│  - product_prices│
│  - audit_logs    │
└──────────────────┘
```

### Project Structure
```
retail_platform/
├── docker-compose.yml        # All services
├── Dockerfile                # App container
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables
├── README.md
└── app/
    ├── main.py               # FastAPI app entry point, lifespan events
    ├── core/
    │   ├── config.py         # Settings via pydantic-settings
    │   ├── database.py       # SQLAlchemy async engine + session
    │   ├── mongodb.py        # Motor async client + index creation
    │   └── security.py       # JWT encode/decode, password hashing
    ├── models/
    │   └── postgres.py       # SQLAlchemy ORM models (all 7 tables)
    ├── schemas/
    │   ├── auth.py           # Pydantic models for auth
    │   ├── product.py        # Pydantic models for products
    │   ├── order.py          # Pydantic models for orders
    │   └── analytics.py      # Pydantic models for analytics responses
    ├── repositories/
    │   ├── base.py           # BaseRepository with audit log helper
    │   ├── tenant.py         # Tenant DB operations
    │   ├── user.py           # User DB operations
    │   ├── product.py        # Product DB operations
    │   ├── order.py          # Order DB operations + stock deduction
    │   └── analytics.py      # All SQL aggregation queries
    ├── services/
    │   ├── auth.py           # Register, login, refresh token logic
    │   ├── product.py        # Product business logic
    │   ├── order.py          # Order business logic
    │   ├── inventory.py      # Snapshot logic
    │   └── analytics.py      # Analytics + KPI cache logic
    ├── routers/
    │   ├── auth.py           # POST /auth/register, login, refresh
    │   ├── products.py       # CRUD /products
    │   ├── orders.py         # POST /orders, GET /orders
    │   ├── inventory.py      # POST /inventory/snapshot
    │   └── analytics.py      # GET /analytics/*
    └── background/
        ├── celery_app.py     # Celery app + beat schedule config
        └── tasks.py          # 3 scheduled background tasks
```

### Multi-Tenant Isolation
Every JWT token contains `tenant_id`. This is extracted on every request via FastAPI dependency injection and passed down through every layer:

```
JWT Token → Middleware extracts tenant_id
                │
                ▼
         CurrentUser object
         { user_id, tenant_id, role, email }
                │
                ▼
    Passed to every Service
                │
                ▼
    Passed to every Repository
                │
                ▼
    Every DB query filters:
    WHERE tenant_id = :tenant_id AND is_deleted = FALSE
```

This means it is **architecturally impossible** for one tenant to access another tenant's data.

---

## Database Schema Diagram

### PostgreSQL Schema

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              tenants                                     │
├────────────────┬─────────────┬──────────────────────────────────────────┤
│ id             │ UUID PK     │                                          │
│ name           │ VARCHAR(255)│ UNIQUE                                   │
│ slug           │ VARCHAR(100)│ UNIQUE  e.g. "nike-store"                │
│ is_active      │ BOOLEAN     │ DEFAULT TRUE                             │
│ is_deleted     │ BOOLEAN     │ DEFAULT FALSE  (soft delete)             │
│ deleted_at     │ TIMESTAMP   │ NULL until deleted                       │
│ created_at     │ TIMESTAMP   │                                          │
│ updated_at     │ TIMESTAMP   │                                          │
└────────────────┴─────────────┴──────────────────────────────────────────┘
        │ 1
        │
        │ N
┌───────▼──────────────────────────────────────────────────────────────────┐
│                               users                                      │
├────────────────┬─────────────┬──────────────────────────────────────────┤
│ id             │ UUID PK     │                                          │
│ tenant_id      │ UUID FK     │ → tenants.id  ON DELETE CASCADE          │
│ email          │ VARCHAR(255)│ UNIQUE per tenant                        │
│ password_hash  │ VARCHAR(255)│                                          │
│ role           │ VARCHAR(50) │ admin / staff / analyst                  │
│ is_active      │ BOOLEAN     │ DEFAULT TRUE                             │
│ is_deleted     │ BOOLEAN     │ DEFAULT FALSE                            │
│ deleted_at     │ TIMESTAMP   │                                          │
│ created_at     │ TIMESTAMP   │                                          │
│ updated_at     │ TIMESTAMP   │                                          │
└────────────────┴─────────────┴──────────────────────────────────────────┘

        │ 1 (tenant)
        │
        │ N
┌───────▼──────────────────────────────────────────────────────────────────┐
│                              products                                    │
├────────────────┬─────────────┬──────────────────────────────────────────┤
│ id             │ UUID PK     │                                          │
│ tenant_id      │ UUID FK     │ → tenants.id  ON DELETE CASCADE          │
│ name           │ VARCHAR(255)│                                          │
│ sku            │ VARCHAR(100)│ UNIQUE per tenant                        │
│ category       │ VARCHAR(100)│ e.g. Footwear, Apparel                   │
│ unit_cost      │ NUMERIC(10,2│ What it costs us                         │
│ selling_price  │ NUMERIC(10,2│ What we sell it for                      │
│ stock_quantity │ INTEGER     │ Current stock level                      │
│ reorder_level  │ INTEGER     │ Alert threshold                          │
│ is_active      │ BOOLEAN     │ DEFAULT TRUE                             │
│ is_deleted     │ BOOLEAN     │ DEFAULT FALSE                            │
│ deleted_at     │ TIMESTAMP   │                                          │
│ created_at     │ TIMESTAMP   │                                          │
│ updated_at     │ TIMESTAMP   │                                          │
└────────────────┴─────────────┴──────────────────────────────────────────┘
        │ 1                              │ 1
        │                               │
        │ N                             │ N
┌───────▼──────────────────┐   ┌────────▼─────────────────────────────────┐
│      product_prices      │   │              order_items                 │
├──────────────┬───────────┤   ├────────────────┬─────────────────────────┤
│ id           │ UUID PK   │   │ id             │ UUID PK                 │
│ tenant_id    │ UUID FK   │   │ tenant_id      │ UUID FK → tenants.id    │
│ product_id   │ UUID FK   │   │ order_id       │ UUID FK → orders.id     │
│ selling_price│ NUMERIC   │   │ product_id     │ UUID FK → products.id   │
│ effective_from│ TIMESTAMP│   │ quantity       │ INTEGER                 │
│ effective_to │ TIMESTAMP │   │ unit_price     │ NUMERIC  (at order time)│
│ created_at   │ TIMESTAMP │   │ unit_cost      │ NUMERIC  (at order time)│
│ updated_at   │ TIMESTAMP │   │ line_revenue   │ NUMERIC  qty * price    │
└──────────────┴───────────┘   │ line_cost      │ NUMERIC  qty * cost     │
                               │ line_profit    │ NUMERIC  revenue - cost │
                               └────────────────┴─────────────────────────┘
                                       │ N
                                       │
                                       │ 1
┌──────────────────────────────────────▼───────────────────────────────────┐
│                               orders                                     │
├────────────────┬─────────────┬──────────────────────────────────────────┤
│ id             │ UUID PK     │                                          │
│ tenant_id      │ UUID FK     │ → tenants.id  ON DELETE CASCADE          │
│ user_id        │ UUID FK     │ → users.id  (who placed the order)       │
│ idempotency_key│ VARCHAR(255)│ UNIQUE per tenant (prevents duplicates)  │
│ status         │ VARCHAR(50) │ pending / confirmed / cancelled          │
│ total_revenue  │ NUMERIC(12,2│ SUM of all line_revenue                  │
│ total_cost     │ NUMERIC(12,2│ SUM of all line_cost                     │
│ total_profit   │ NUMERIC(12,2│ total_revenue - total_cost               │
│ ordered_at     │ TIMESTAMP   │                                          │
│ is_deleted     │ BOOLEAN     │ DEFAULT FALSE                            │
│ deleted_at     │ TIMESTAMP   │                                          │
│ created_at     │ TIMESTAMP   │                                          │
│ updated_at     │ TIMESTAMP   │                                          │
└────────────────┴─────────────┴──────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                             audit_logs                                   │
├────────────────┬─────────────┬──────────────────────────────────────────┤
│ id             │ UUID PK     │                                          │
│ tenant_id      │ UUID FK     │ → tenants.id                             │
│ user_id        │ UUID          who performed the action                 │
│ action         │ VARCHAR(50) │ CREATE / UPDATE / DELETE                 │
│ entity         │ VARCHAR(50) │ order / product / user                   │
│ entity_id      │ UUID        │ which record was affected                │
│ old_data       │ JSONB       │ state before change                      │
│ new_data       │ JSONB       │ state after change                       │
│ ip_address     │ VARCHAR(50) │                                          │
│ created_at     │ TIMESTAMP   │                                          │
└────────────────┴─────────────┴──────────────────────────────────────────┘
```

### MongoDB Schema

```
Collection: inventory_snapshots
┌─────────────────────────────────────────────────────┐
│ {                                                   │
│   "_id":             ObjectId,                      │
│   "tenant_id":       "uuid-string",                 │
│   "product_id":      "uuid-string",                 │
│   "product_name":    "Nike Air Max 90",             │
│   "sku":             "NK-AM90-001",                 │
│   "category":        "Footwear",                    │
│   "quantity_on_hand": 150,                          │
│   "reorder_level":   20,                            │
│   "snapshot_date":   "2024-01-15",                  │
│   "created_at":      ISODate                        │
│ }                                                   │
│ Index: { tenant_id:1, product_id:1, snapshot_date:-1│
│ }  UNIQUE                                           │
└─────────────────────────────────────────────────────┘

Collection: daily_sales_summary
┌─────────────────────────────────────────────────────┐
│ {                                                   │
│   "_id":                   ObjectId,                │
│   "tenant_id":             "uuid-string",           │
│   "date":                  "2024-01-15",            │
│   "total_orders":          45,                      │
│   "total_revenue":         12500.00,                │
│   "total_cost":            7800.00,                 │
│   "total_profit":          4700.00,                 │
│   "gross_margin_percent":  37.6,                    │
│   "updated_at":            ISODate                  │
│ }                                                   │
│ Index: { tenant_id:1, date:-1 }  UNIQUE             │
└─────────────────────────────────────────────────────┘

Collection: kpi_cache
┌─────────────────────────────────────────────────────┐
│ {                                                   │
│   "_id":          ObjectId,                         │
│   "tenant_id":    "uuid-string",                    │
│   "kpi_type":     "profitability",                  │
│   "period":       "2024-01",                        │
│   "computed_at":  ISODate,                          │
│   "expires_at":   ISODate,   ← TTL auto-deletes     │
│   "data": {                                         │
│     "total_revenue":        125000.00,              │
│     "total_cost":           78000.00,               │
│     "gross_profit":         47000.00,               │
│     "gross_margin_percent": 37.6,                   │
│     "total_orders":         320,                    │
│     "avg_order_value":      390.62                  │
│   }                                                 │
│ }                                                   │
│ Index: { tenant_id:1, kpi_type:1, period:1 } UNIQUE │
│ Index: { expires_at:1 } expireAfterSeconds=0        │
└─────────────────────────────────────────────────────┘
```

---

## Index Strategy

### PostgreSQL Indexes

```sql
-- ── users ──────────────────────────────────────────────────────────────
-- Login lookup: find user by tenant + email
CREATE UNIQUE INDEX uq_user_tenant_email ON users(tenant_id, email);
CREATE INDEX idx_users_tenant_id ON users(tenant_id);

-- ── products ───────────────────────────────────────────────────────────
-- SKU lookup within tenant
CREATE UNIQUE INDEX uq_product_tenant_sku ON products(tenant_id, sku);

-- List all products for a tenant
CREATE INDEX idx_products_tenant_id ON products(tenant_id);

-- Filter products by category within tenant
CREATE INDEX idx_products_category ON products(tenant_id, category);

-- ── product_prices ─────────────────────────────────────────────────────
-- Find current active price for a product
CREATE INDEX idx_prices_product_id ON product_prices(product_id, effective_from);
CREATE INDEX idx_prices_tenant_id ON product_prices(tenant_id);

-- ── orders ─────────────────────────────────────────────────────────────
-- Idempotency check: is this key already used?
CREATE UNIQUE INDEX uq_order_idempotency ON orders(tenant_id, idempotency_key);

-- List orders for a tenant
CREATE INDEX idx_orders_tenant_id ON orders(tenant_id);

-- Date range queries for analytics (profitability, demand trend)
-- Most important index — used by every analytics query
CREATE INDEX idx_orders_ordered_at ON orders(tenant_id, ordered_at);

-- Filter by status
CREATE INDEX idx_orders_status ON orders(tenant_id, status);

-- ── order_items ────────────────────────────────────────────────────────
-- Load items for a specific order
CREATE INDEX idx_order_items_order_id ON order_items(order_id);

-- Sales per product analytics
CREATE INDEX idx_order_items_product_id ON order_items(tenant_id, product_id);

-- ── audit_logs ─────────────────────────────────────────────────────────
-- Audit trail per tenant
CREATE INDEX idx_audit_tenant_id ON audit_logs(tenant_id);

-- Find all changes to a specific record
CREATE INDEX idx_audit_entity ON audit_logs(entity, entity_id);
```

### Why These Indexes?

| Index | Query it supports | Without index |
|-------|------------------|---------------|
| `orders(tenant_id, ordered_at)` | Profitability date range | Full table scan ❌ |
| `order_items(tenant_id, product_id)` | Sales per product | Full table scan ❌ |
| `orders(tenant_id, idempotency_key)` | Duplicate order check | Full table scan ❌ |
| `products(tenant_id, category)` | Category filter | Full table scan ❌ |
| `users(tenant_id, email)` | Login lookup | Full table scan ❌ |

### EXPLAIN Analysis

```sql
-- Profitability query EXPLAIN
EXPLAIN ANALYZE
SELECT
    COUNT(o.id),
    SUM(o.total_revenue),
    SUM(o.total_profit)
FROM orders o
WHERE o.tenant_id  = 'nike-uuid'
  AND o.ordered_at >= '2024-01-01'
  AND o.ordered_at <= '2024-12-31'
  AND o.status     = 'confirmed'
  AND o.is_deleted = FALSE;

-- Result with index:
-- Index Scan using idx_orders_ordered_at on orders
-- Index Cond: tenant_id = 'nike-uuid' AND ordered_at BETWEEN ...
-- Rows: ~500  Cost: 0.43..18.50  ✅ Fast

-- Result without index:
-- Seq Scan on orders
-- Filter: tenant_id = ... AND ordered_at BETWEEN ...
-- Rows: 100000  Cost: 0.00..3200.00  ❌ Slow
```

### MongoDB Indexes

```javascript
// Snapshot lookup by product + date
db.inventory_snapshots.createIndex(
    { tenant_id: 1, product_id: 1, snapshot_date: -1 },
    { unique: true }
)
// Supports: find latest snapshot per product

// Daily summary lookup by date
db.daily_sales_summary.createIndex(
    { tenant_id: 1, date: -1 },
    { unique: true }
)
// Supports: get summary for a date range

// KPI cache lookup
db.kpi_cache.createIndex(
    { tenant_id: 1, kpi_type: 1, period: 1 },
    { unique: true }
)
// Supports: instant cache hit check

// TTL index — auto-deletes expired cache
db.kpi_cache.createIndex(
    { expires_at: 1 },
    { expireAfterSeconds: 0 }
)
// MongoDB background job auto-deletes documents
// where expires_at < current time
```

---

## Query Optimization Explanation

### Rule: All Aggregation Done Inside the Database

We never load raw rows into Python and compute in application code.

```python
# ❌ WRONG — loads all rows into Python memory
orders = await db.execute(select(Order).where(...))
total_revenue = sum(order.total_revenue for order in orders)  # Python loop

# ✅ CORRECT — aggregation happens inside PostgreSQL
result = await db.execute(text("""
    SELECT SUM(total_revenue) AS total_revenue
    FROM orders
    WHERE tenant_id = :tenant_id
    AND ordered_at BETWEEN :from AND :to
"""))
```

### Profitability Query Optimization

```sql
-- Single query handles everything:
-- revenue, cost, profit, margin%, avg order value
-- No N+1, no multiple round trips, no Python math

SELECT
    COUNT(o.id)                                          AS total_orders,
    COALESCE(SUM(o.total_revenue), 0)                   AS total_revenue,
    COALESCE(SUM(o.total_cost), 0)                      AS total_cost,
    COALESCE(SUM(o.total_profit), 0)                    AS gross_profit,
    CASE
        WHEN SUM(o.total_revenue) > 0
        THEN ROUND((SUM(o.total_profit) / SUM(o.total_revenue)) * 100, 2)
        ELSE 0
    END                                                  AS gross_margin_percent,
    CASE
        WHEN COUNT(o.id) > 0
        THEN ROUND(SUM(o.total_revenue) / COUNT(o.id), 2)
        ELSE 0
    END                                                  AS avg_order_value
FROM orders o
WHERE
    o.tenant_id  = :tenant_id
    AND o.is_deleted = FALSE
    AND o.status     = 'confirmed'
    AND o.ordered_at >= :from_date
    AND o.ordered_at <= :to_date
```

### Year-over-Year Demand Trend Optimization

```sql
-- Uses CTE to compute both years in ONE query
-- No separate queries, no Python joining

WITH current_year AS (
    SELECT
        DATE(ordered_at)      AS sale_date,
        COUNT(DISTINCT o.id)  AS order_count,
        SUM(oi.quantity)      AS units_sold,
        SUM(o.total_revenue)  AS revenue
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.id
    WHERE tenant_id = :tenant_id
      AND EXTRACT(YEAR FROM ordered_at) = EXTRACT(YEAR FROM NOW())
    GROUP BY DATE(ordered_at)
),
previous_year AS (
    SELECT
        DATE(ordered_at)      AS sale_date,
        COUNT(DISTINCT o.id)  AS order_count,
        SUM(oi.quantity)      AS units_sold,
        SUM(o.total_revenue)  AS revenue
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.id
    WHERE tenant_id = :tenant_id
      AND EXTRACT(YEAR FROM ordered_at) = EXTRACT(YEAR FROM NOW()) - 1
    GROUP BY DATE(ordered_at)
)
SELECT 'current' AS year_type, * FROM current_year
UNION ALL
SELECT 'previous' AS year_type, * FROM previous_year
```

### Avoiding N+1 Queries

```python
# ❌ N+1 Problem — 1 query for orders + N queries for items
orders = await db.execute(select(Order))
for order in orders:
    items = await db.execute(  # ← fires once per order!
        select(OrderItem).where(OrderItem.order_id == order.id)
    )

# ✅ Fixed — single query with JOIN using selectinload
result = await db.execute(
    select(Order)
    .options(selectinload(Order.items))  # ← loads all items in 1 extra query
    .where(Order.tenant_id == tenant_id)
)
```

### KPI Cache Strategy

```
Analytics Request
        │
        ▼
Check MongoDB kpi_cache
        │
        ├── HIT  → Return instantly (milliseconds) ✅
        │
        └── MISS → Query PostgreSQL
                        │
                        ▼
                   Compute result
                        │
                        ▼
                   Save to kpi_cache
                   with expires_at
                        │
                        ▼
                   Return result ✅
```

This means heavy analytical queries run **at most once per hour** instead of on every request.

### Pagination to Handle Large Datasets

```python
# All list endpoints are paginated — never return all rows
query = (
    select(Order)
    .where(Order.tenant_id == tenant_id)
    .order_by(Order.ordered_at.desc())
    .offset((page - 1) * page_size)   # skip previous pages
    .limit(page_size)                  # max 100 rows per request
)
```

---

## Why MongoDB Instead of PostgreSQL

### inventory_snapshots
| Reason | Explanation |
|--------|-------------|
| Time-series data | Each snapshot is a point-in-time record. MongoDB handles this naturally |
| Flexible schema | Different products may have different attributes in future |
| Fast reads | Single document fetch by product_id + date is very fast |
| No joins needed | Each snapshot is self-contained with all product info |

### daily_sales_summary
| Reason | Explanation |
|--------|-------------|
| Pre-aggregated | Already computed — just needs to be stored and fetched |
| Read-heavy | Dashboard reads this many times, writes happen once daily |
| Flexible structure | Can store embedded arrays like top_products without schema change |
| Decoupled from transactions | Analytics data is separate concern from transactional data |

### kpi_cache
| Reason | Explanation |
|--------|-------------|
| TTL index support | MongoDB natively auto-deletes expired documents |
| No schema migration | Adding new KPI types needs no ALTER TABLE |
| Fast key-value lookup | Find by tenant_id + kpi_type + period is instant |
| Cache-friendly | Document model perfectly matches cache use case |

---

## Background Processing

### Why Celery over FastAPI BackgroundTasks?

| Feature | Celery | FastAPI BackgroundTasks |
|---------|--------|------------------------|
| Scheduled tasks (cron) | ✅ Yes (Celery Beat) | ❌ No |
| Retry on failure | ✅ Yes | ❌ No |
| Task monitoring | ✅ Yes (Flower) | ❌ No |
| Distributed workers | ✅ Yes | ❌ No |
| Production ready | ✅ Yes | ⚠️ Simple tasks only |

Celery is chosen because this is a **production-grade** application requiring scheduled jobs, retry logic, and distributed processing.

### Scheduled Tasks

| Task | Schedule | What it does |
|------|----------|-------------|
| `aggregate_daily_sales` | Daily midnight | Reads yesterday's confirmed orders from PostgreSQL, computes totals, saves to MongoDB `daily_sales_summary` |
| `take_daily_inventory_snapshot` | Daily 11:55 PM | Reads current `stock_quantity` from all products, saves to MongoDB `inventory_snapshots` |
| `compute_kpi_cache` | Every hour | Pre-computes profitability KPIs for current month, saves to MongoDB `kpi_cache` with 1-hour TTL |

---

## Setup Instructions

### Prerequisites
- Docker
- Docker Compose

### 1. Clone Repository
```bash
git clone <your-repo-url>
cd retail_platform
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env and set a strong SECRET_KEY
```


### 3. Start All Services
```bash
docker-compose up --build
```

This starts:
- **FastAPI app** on port 8000
- **PostgreSQL** on port 5432
- **MongoDB** on port 27017
- **Redis** on port 6379
- **Celery Worker** (background tasks)
- **Celery Beat** (task scheduler)

### 4. Verify Everything is Running
```bash
docker-compose ps
# All services should show: Up (healthy)
```

### 5. Access API Documentation
```
http://localhost:8000/docs       ← Swagger UI (interactive)
```

### 6. Quick Start — Register and Test
```bash
# Register a new tenant
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_name": "Nike Store",
    "tenant_slug": "nike-store",
    "email": "admin@nike.com",
    "password": "nike1234",
    "role": "admin"
  }'

# Login
curl -X POST "http://localhost:8000/auth/login?tenant_slug=nike-store" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@nike.com", "password": "nike1234"}'

# Use the access_token from login response for all further requests
# Add header: Authorization: Bearer <access_token>

# Create a product
curl -X POST http://localhost:8000/products \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Nike Air Max 90",
    "sku": "NK-AM90-001",
    "category": "Footwear",
    "unit_cost": 45.00,
    "selling_price": 120.00,
    "stock_quantity": 200,
    "reorder_level": 20
  }'

# Place an order
curl -X POST http://localhost:8000/orders \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "order-001",
    "items": [
      {"product_id": "<product_id>", "quantity": 2}
    ]
  }'

# Get profitability analytics
curl "http://localhost:8000/analytics/profitability?from_date=2024-01-01&to_date=2024-12-31" \
  -H "Authorization: Bearer <access_token>"
```

### 7. Stop Services
```bash
docker-compose down          # stop containers
docker-compose down -v       # stop + delete all data volumes
```

---

## API Documentation

### Authentication Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register new tenant + admin user |
| POST | `/auth/login?tenant_slug=X` | Login, receive access + refresh tokens |
| POST | `/auth/refresh` | Get new access token using refresh token |

### Product Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/products` | Create a new product |
| GET | `/products` | List products (paginated, filterable) |
| GET | `/products/{id}` | Get single product |
| PATCH | `/products/{id}` | Update product (partial) |
| POST | `/products/{id}/adjust-stock` | Add or reduce stock |
| DELETE | `/products/{id}` | Soft delete product |

### Order Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/orders` | Create order (idempotent, transactional) |
| GET | `/orders` | List orders (paginated) |
| GET | `/orders/{id}` | Get single order with items |

### Inventory Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/inventory/snapshot` | Take daily inventory snapshot to MongoDB |

### Analytics Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/analytics/profitability?from_date=&to_date=` | Revenue, cost, gross profit, margin % |
| GET | `/analytics/demand-trend` | Daily sales with year-over-year comparison |
| GET | `/analytics/inventory-depletion` | Estimated days to stock-out per product |

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health check |

---