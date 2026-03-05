import uuid
from datetime import datetime
from sqlalchemy import (Column, String, Boolean, DateTime, Numeric,
    Integer, ForeignKey, UniqueConstraint, Index)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base

def gen_uuid(): return str(uuid.uuid4())

class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class SoftDeleteMixin:
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

class Tenant(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "tenants"
    id        = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name      = Column(String(255), nullable=False, unique=True)
    slug      = Column(String(100), nullable=False, unique=True)
    is_active = Column(Boolean, default=True, nullable=False)
    users    = relationship("User", back_populates="tenant")
    products = relationship("Product", back_populates="tenant")
    orders   = relationship("Order", back_populates="tenant")

class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),
        Index("idx_users_tenant_id", "tenant_id"),
    )
    id            = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tenant_id     = Column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    email         = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role          = Column(String(50), default="staff", nullable=False)
    is_active     = Column(Boolean, default=True, nullable=False)
    tenant = relationship("Tenant", back_populates="users")

class Product(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="uq_product_tenant_sku"),
        Index("idx_products_tenant_id", "tenant_id"),
        Index("idx_products_category", "tenant_id", "category"),
    )
    id             = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tenant_id      = Column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name           = Column(String(255), nullable=False)
    sku            = Column(String(100), nullable=False)
    category       = Column(String(100), nullable=True)
    unit_cost      = Column(Numeric(10, 2), nullable=False)
    selling_price  = Column(Numeric(10, 2), nullable=False)
    stock_quantity = Column(Integer, default=0, nullable=False)
    reorder_level  = Column(Integer, default=10, nullable=False)
    is_active      = Column(Boolean, default=True, nullable=False)
    tenant      = relationship("Tenant", back_populates="products")
    prices      = relationship("ProductPrice", back_populates="product")
    order_items = relationship("OrderItem", back_populates="product")

class ProductPrice(Base, TimestampMixin):
    __tablename__ = "product_prices"
    __table_args__ = (
        Index("idx_prices_product_id", "product_id", "effective_from"),
        Index("idx_prices_tenant_id", "tenant_id"),
    )
    id             = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tenant_id      = Column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    product_id     = Column(UUID(as_uuid=False), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    selling_price  = Column(Numeric(10, 2), nullable=False)
    effective_from = Column(DateTime, default=datetime.utcnow, nullable=False)
    effective_to   = Column(DateTime, nullable=True)
    product = relationship("Product", back_populates="prices")

class Order(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_order_idempotency"),
        Index("idx_orders_tenant_id", "tenant_id"),
        Index("idx_orders_ordered_at", "tenant_id", "ordered_at"),
        Index("idx_orders_status", "tenant_id", "status"),
    )
    id              = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tenant_id       = Column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id         = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    idempotency_key = Column(String(255), nullable=False)
    status          = Column(String(50), default="confirmed", nullable=False)
    total_revenue   = Column(Numeric(12, 2), default=0, nullable=False)
    total_cost      = Column(Numeric(12, 2), default=0, nullable=False)
    total_profit    = Column(Numeric(12, 2), default=0, nullable=False)
    ordered_at      = Column(DateTime, default=datetime.utcnow, nullable=False)
    tenant = relationship("Tenant", back_populates="orders")
    items  = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        Index("idx_order_items_order_id", "order_id"),
        Index("idx_order_items_product_id", "tenant_id", "product_id"),
    )
    id           = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tenant_id    = Column(UUID(as_uuid=False), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    order_id     = Column(UUID(as_uuid=False), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id   = Column(UUID(as_uuid=False), ForeignKey("products.id"), nullable=False)
    quantity     = Column(Integer, nullable=False)
    unit_price   = Column(Numeric(10, 2), nullable=False)
    unit_cost    = Column(Numeric(10, 2), nullable=False)
    line_revenue = Column(Numeric(12, 2), nullable=False)
    line_cost    = Column(Numeric(12, 2), nullable=False)
    line_profit  = Column(Numeric(12, 2), nullable=False)
    order   = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_tenant_id", "tenant_id"),
        Index("idx_audit_entity", "entity", "entity_id"),
    )
    id         = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    tenant_id  = Column(UUID(as_uuid=False), ForeignKey("tenants.id"), nullable=True)
    user_id    = Column(UUID(as_uuid=False), nullable=True)
    action     = Column(String(50), nullable=False)
    entity     = Column(String(50), nullable=False)
    entity_id  = Column(UUID(as_uuid=False), nullable=True)
    old_data   = Column(JSONB, nullable=True)
    new_data   = Column(JSONB, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)