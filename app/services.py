"""Вся бизнес-логика учёта. Роутеры только валидируют вход и вызывают функции отсюда.

Ключевые принципы:
- единственный источник количеств — таблица Stock;
- "в пути" — это статус операции, а не остаток на каком-то складе;
- идемпотентность через статус: повторный переход выдаёт 409;
- нехватка отказывает с подсказкой, где товар есть;
- журнал append-only.
"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .models import utcnow

STATUS_TRANSFER_CREATED = "CREATED"
STATUS_TRANSFER_ACCEPTED = "ACCEPTED"
STATUS_RESERVATION_RESERVED = "RESERVED"
STATUS_RESERVATION_SHIPPED = "SHIPPED"
STATUS_RESERVATION_CANCELLED = "CANCELLED"
STATUS_FBO_IN_TRANSIT = "IN_TRANSIT"
STATUS_FBO_RECEIVED = "RECEIVED"


def _get_or_404(db: Session, model, obj_id: int, what: str):
    obj = db.get(model, obj_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{what} не найден")
    return obj


def _ensure_stock(db: Session, warehouse_id: int, sku_id: int) -> models.Stock:
    stock = db.execute(
        select(models.Stock).where(
            models.Stock.warehouse_id == warehouse_id,
            models.Stock.sku_id == sku_id,
        )
    ).scalar_one_or_none()
    if stock is None:
        stock = models.Stock(warehouse_id=warehouse_id, sku_id=sku_id, physical=0, reserved=0)
        db.add(stock)
        db.flush()
    return stock


def _log(
    db: Session,
    operation: str,
    sku_id: int | None,
    warehouse_id: int | None,
    quantity: int,
    details: str,
) -> None:
    db.add(
        models.OperationLog(
            operation=operation,
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            quantity=quantity,
            details=details,
        )
    )


def shortage_hint(db: Session, warehouse_id: int, sku_id: int, quantity: int) -> str:
    """Сообщение о нехватке с подсказкой, где нужное количество доступно."""
    stock = _ensure_stock(db, warehouse_id, sku_id)
    detail = f"Недостаточно товара: доступно {stock.available}, требуется {quantity}."
    rows = db.execute(
        select(models.Stock, models.Warehouse)
        .join(models.Warehouse, models.Stock.warehouse_id == models.Warehouse.id)
        .where(
            models.Stock.sku_id == sku_id,
            models.Stock.warehouse_id != warehouse_id,
            models.Warehouse.is_active.is_(True),
        )
    ).all()
    alternatives = [
        f"«{wh.name}» — {row.available} шт." for row, wh in rows if row.available > 0
    ]
    if alternatives:
        detail += " Товар есть на складах: " + ", ".join(alternatives) + "."
    else:
        detail += " Других складов с доступным товаром нет."
    return detail


def receive_stock(db: Session, *, warehouse_id: int, sku_id: int, quantity: int) -> models.Stock:
    """Приход: увеличение физического остатка."""
    warehouse = _get_or_404(db, models.Warehouse, warehouse_id, "Склад")
    _get_or_404(db, models.Sku, sku_id, "Товар")
    stock = _ensure_stock(db, warehouse_id, sku_id)
    stock.physical += quantity
    _log(db, "ПРИХОД", sku_id, warehouse_id, quantity, f"Принято на склад «{warehouse.name}»")
    db.commit()
    return stock


def create_transfer(
    db: Session, *, from_warehouse_id: int, to_warehouse_id: int, sku_id: int, quantity: int
) -> models.StockTransfer:
    """Перемещение: списание у отправителя, товар в пути, получатель ещё не видит."""
    if from_warehouse_id == to_warehouse_id:
        raise HTTPException(status_code=409, detail="Склады отправления и назначения должны различаться")
    src = _get_or_404(db, models.Warehouse, from_warehouse_id, "Склад-отправитель")
    dst = _get_or_404(db, models.Warehouse, to_warehouse_id, "Склад-получатель")
    for wh in (src, dst):
        if not wh.is_active:
            raise HTTPException(status_code=409, detail=f"Склад «{wh.name}» неактивен")
    _get_or_404(db, models.Sku, sku_id, "Товар")

    stock = _ensure_stock(db, from_warehouse_id, sku_id)
    if quantity > stock.available:
        raise HTTPException(status_code=409, detail=shortage_hint(db, from_warehouse_id, sku_id, quantity))

    stock.physical -= quantity
    transfer = models.StockTransfer(
        sku_id=sku_id,
        from_warehouse_id=from_warehouse_id,
        to_warehouse_id=to_warehouse_id,
        quantity=quantity,
        status=STATUS_TRANSFER_CREATED,
    )
    db.add(transfer)
    db.flush()
    _log(
        db, "ПЕРЕМЕЩЕНИЕ", sku_id, from_warehouse_id, quantity,
        f"Отправлено со склада «{src.name}» на «{dst.name}», в пути",
    )
    db.commit()
    db.refresh(transfer)
    return transfer


def accept_transfer(db: Session, transfer_id: int) -> models.StockTransfer:
    """Приёмка перемещения. Повторная приёмка отклоняется — идемпотентность через статус."""
    transfer = _get_or_404(db, models.StockTransfer, transfer_id, "Перемещение")
    if transfer.status != STATUS_TRANSFER_CREATED:
        raise HTTPException(status_code=409, detail="Перемещение уже принято")
    transfer.status = STATUS_TRANSFER_ACCEPTED
    transfer.accepted_at = utcnow()
    stock = _ensure_stock(db, transfer.to_warehouse_id, transfer.sku_id)
    stock.physical += transfer.quantity
    _log(
        db, "ПРИЁМКА ПЕРЕМЕЩЕНИЯ", transfer.sku_id, transfer.to_warehouse_id, transfer.quantity,
        f"Принято на складе, перемещение №{transfer.id}",
    )
    db.commit()
    db.refresh(transfer)
    return transfer


def create_reservation(db: Session, *, warehouse_id: int, sku_id: int, quantity: int) -> models.Reservation:
    """Резерв FBS: reserved растёт, available падает, физический остаток не трогается."""
    warehouse = _get_or_404(db, models.Warehouse, warehouse_id, "Склад")
    if not warehouse.is_active:
        raise HTTPException(status_code=409, detail=f"Склад «{warehouse.name}» неактивен")
    _get_or_404(db, models.Sku, sku_id, "Товар")
    stock = _ensure_stock(db, warehouse_id, sku_id)
    if quantity > stock.available:
        raise HTTPException(status_code=409, detail=shortage_hint(db, warehouse_id, sku_id, quantity))
    stock.reserved += quantity
    reservation = models.Reservation(warehouse_id=warehouse_id, sku_id=sku_id, quantity=quantity)
    db.add(reservation)
    db.flush()
    _log(
        db, "РЕЗЕРВ FBS", sku_id, warehouse_id, quantity,
        f"Зарезервировано на складе «{warehouse.name}»",
    )
    db.commit()
    db.refresh(reservation)
    return reservation


def ship_reservation(db: Session, reservation_id: int) -> models.Reservation:
    """Отгрузка резерва: физический сток уходит, товар едет к клиенту."""
    reservation = _get_or_404(db, models.Reservation, reservation_id, "Резерв")
    if reservation.status != STATUS_RESERVATION_RESERVED:
        raise HTTPException(status_code=409, detail="Резерв уже отгружен или отменён")
    reservation.status = STATUS_RESERVATION_SHIPPED
    reservation.shipped_at = utcnow()
    stock = _ensure_stock(db, reservation.warehouse_id, reservation.sku_id)
    stock.physical -= reservation.quantity
    stock.reserved -= reservation.quantity
    _log(
        db, "ОТГРУЗКА FBS", reservation.sku_id, reservation.warehouse_id, reservation.quantity,
        f"Отгружено клиенту, резерв №{reservation.id}",
    )
    db.commit()
    db.refresh(reservation)
    return reservation


def cancel_reservation(db: Session, reservation_id: int) -> models.Reservation:
    """Отмена резерва: бронь снимается, available возвращается. Физика не менялась."""
    reservation = _get_or_404(db, models.Reservation, reservation_id, "Резерв")
    if reservation.status != STATUS_RESERVATION_RESERVED:
        raise HTTPException(status_code=409, detail="Отменить можно только зарезервированный товар")
    reservation.status = STATUS_RESERVATION_CANCELLED
    reservation.cancelled_at = utcnow()
    stock = _ensure_stock(db, reservation.warehouse_id, reservation.sku_id)
    stock.reserved -= reservation.quantity
    _log(
        db, "ОТМЕНА РЕЗЕРВА", reservation.sku_id, reservation.warehouse_id, reservation.quantity,
        f"Бронь снята, резерв №{reservation.id}",
    )
    db.commit()
    db.refresh(reservation)
    return reservation


def create_fbo_shipment(db: Session, *, warehouse_id: int, sku_id: int, quantity: int) -> models.FboShipment:
    """Отправка на маркетплейс: списание со склада, товар в пути на FBO."""
    warehouse = _get_or_404(db, models.Warehouse, warehouse_id, "Склад")
    if not warehouse.is_active:
        raise HTTPException(status_code=409, detail=f"Склад «{warehouse.name}» неактивен")
    _get_or_404(db, models.Sku, sku_id, "Товар")
    stock = _ensure_stock(db, warehouse_id, sku_id)
    if quantity > stock.available:
        raise HTTPException(status_code=409, detail=shortage_hint(db, warehouse_id, sku_id, quantity))
    stock.physical -= quantity
    shipment = models.FboShipment(from_warehouse_id=warehouse_id, sku_id=sku_id, quantity=quantity)
    db.add(shipment)
    db.flush()
    _log(
        db, "ОТПРАВКА FBO", sku_id, warehouse_id, quantity,
        f"Отправлено на маркетплейс со склада «{warehouse.name}», в пути",
    )
    db.commit()
    db.refresh(shipment)
    return shipment


def receive_fbo(db: Session, shipment_id: int) -> models.FboShipment:
    """Приёмка маркетплейсом. Повторная приёмка отклоняется."""
    shipment = _get_or_404(db, models.FboShipment, shipment_id, "Отправка FBO")
    if shipment.status != STATUS_FBO_IN_TRANSIT:
        raise HTTPException(status_code=409, detail="Отправка уже принята маркетплейсом")
    shipment.status = STATUS_FBO_RECEIVED
    shipment.received_at = utcnow()
    _log(
        db, "ПРИЁМКА FBO", shipment.sku_id, shipment.from_warehouse_id, shipment.quantity,
        f"Принято маркетплейсом, отправка №{shipment.id}",
    )
    db.commit()
    db.refresh(shipment)
    return shipment


def soft_delete_warehouse(db: Session, warehouse_id: int) -> models.Warehouse:
    """Мягкое удаление: остатки и история сохраняются, склад помечается неактивным."""
    warehouse = _get_or_404(db, models.Warehouse, warehouse_id, "Склад")
    if not warehouse.is_active:
        raise HTTPException(status_code=409, detail="Склад уже неактивен")
    warehouse.is_active = False
    _log(
        db,
        "УДАЛЕНИЕ СКЛАДА",
        sku_id=None,
        warehouse_id=warehouse.id,
        quantity=0,
        details=f"Склад «{warehouse.name}» помечен неактивным, остатки и история сохранены",
    )
    db.commit()
    db.refresh(warehouse)
    return warehouse
