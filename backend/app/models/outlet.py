from sqlalchemy import Boolean, Float, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin


class Outlet(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "outlets"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    area: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    address_text: Mapped[str] = mapped_column(String(500), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    opening_time: Mapped[Time] = mapped_column(Time, nullable=False)
    closing_time: Mapped[Time] = mapped_column(Time, nullable=False)
    delivery_radius_km: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    stock: Mapped[list["OutletStock"]] = relationship(back_populates="outlet", cascade="all, delete-orphan")
