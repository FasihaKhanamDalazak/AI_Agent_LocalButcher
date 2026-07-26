import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class OrderStatus(Base, UUIDPKMixin):
    """
    Reference table driving modification/cancellation rules. Seeded with
    pending / confirmed / packed / out_for_delivery / delivered / cancelled
    in a data migration (Step 2c). Change the rules by editing rows here,
    not by editing code.
    """

    __tablename__ = "order_statuses"

    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    is_modifiable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_cancellable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class Order(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "orders"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    outlet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outlets.id"), nullable=False)
    address_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("addresses.id"), nullable=True)  # null if pickup
    status_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order_statuses.id"), nullable=False)

    fulfillment_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "delivery" | "pickup"
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    # Customer-facing sequential number ("order #1000"), separate from the
    # UUID primary key on purpose — the UUID is what the system uses
    # internally and never leaks patterns; this is what a human reads back
    # in conversation or on a receipt. Backed by a Postgres sequence created
    # in a hand-written migration (see migrations/versions — same pattern as
    # the order_statuses seed).
    order_number: Mapped[int] = mapped_column(
        Integer, unique=True, nullable=False, server_default=text("nextval('orders_order_number_seq')")
    )

    # Placeholder ETA heuristic (prep + delivery time estimate) set once at
    # checkout — see order_service.checkout(). Not recalculated as the order
    # progresses. Replace with real logistics/rider-tracking data later;
    # everything downstream (schemas, greeting) already reads from these two
    # columns, so that swap won't touch calling code.
    eta_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    eta_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    status: Mapped["OrderStatus"] = relationship()
    outlet: Mapped["Outlet"] = relationship()
    # Staff-dashboard read only (see staff_order_to_read) — customer-facing
    # OrderRead never surfaces another user's data, so nothing outside the
    # staff path should eager-load or expose this relationship.
    user: Mapped["User"] = relationship()


class OrderItem(Base, UUIDPKMixin):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    price_at_order: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()
