import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Product(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)  # "kg", "piece", ...
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    # Configurable per-order cap — checked before add-to-cart and before order placement.
    # Lives in the DB (not code) so it can change without a redeploy.
    max_qty_per_order: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    stock_by_outlet: Mapped[list["OutletStock"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class OutletStock(Base, UUIDPKMixin, TimestampMixin):
    """Inventory is per-outlet, never global. One row per (outlet, product) pair."""

    __tablename__ = "outlet_stock"
    __table_args__ = (UniqueConstraint("outlet_id", "product_id", name="uq_outlet_product"),)

    outlet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outlets.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)

    # Optimistic-locking counter — incremented on every write, checked in the
    # WHERE clause of stock-deduction updates to prevent overselling under
    # concurrent orders. See order placement logic in Step 3.
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    outlet: Mapped["Outlet"] = relationship(back_populates="stock")
    product: Mapped["Product"] = relationship(back_populates="stock_by_outlet")
