"""Модели SQLAlchemy 2.0: склады, товары, остатки, операции, журнал."""
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    """Время всегда в UTC с таймзоной — никаких наивных дат."""
    return datetime.now(UTC)


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    stocks: Mapped[list["Stock"]] = relationship(back_populates="warehouse")


class Sku(Base):
    """Товарная позиция: артикул + название."""

    __tablename__ = "skus"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    stocks: Mapped[list["Stock"]] = relationship(back_populates="sku")


class Stock(Base):
    """Остаток пары склад+товар. Единственный источник количеств.

    available не хранится: это производное значение (physical - reserved),
    оно не может разъехаться с исходными, потому что его физически нет.
    """

    __tablename__ = "stocks"
    __table_args__ = (UniqueConstraint("warehouse_id", "sku_id", name="uq_stock_wh_sku"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id"))
    physical: Mapped[int] = mapped_column(default=0)
    reserved: Mapped[int] = mapped_column(default=0)

    warehouse: Mapped["Warehouse"] = relationship(back_populates="stocks")
    sku: Mapped["Sku"] = relationship(back_populates="stocks")

    @property
    def available(self) -> int:
        return self.physical - self.reserved


class StockTransfer(Base):
    """Перемещение между складами ФФ. Товар в пути не числится ни на одном складе."""

    __tablename__ = "stock_transfers"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id"))
    from_warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    to_warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    quantity: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(default="CREATED")  # CREATED -> ACCEPTED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Reservation(Base):
    """Резерв FBS под заказ клиента. Отмена возможна только до отгрузки."""

    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id"))
    quantity: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(default="RESERVED")  # RESERVED -> SHIPPED | CANCELLED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FboShipment(Base):
    """Отправка на склад маркетплейса (FBO)."""

    __tablename__ = "fbo_shipments"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id"))
    quantity: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(default="IN_TRANSIT")  # IN_TRANSIT -> RECEIVED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OperationLog(Base):
    """Append-only журнал: записи только добавляются, не изменяются и не удаляются."""

    __tablename__ = "operation_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    operation: Mapped[str] = mapped_column()
    sku_id: Mapped[int | None] = mapped_column(ForeignKey("skus.id"), nullable=True)
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    quantity: Mapped[int] = mapped_column(default=0)
    details: Mapped[str] = mapped_column(default="")
