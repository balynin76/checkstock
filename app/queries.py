"""Read-запросы: списки остатков, операций и журнала."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .schemas import FboShipmentOut, JournalOut, ReservationOut, StockOut, TransferOut


def _transit_ff(db: Session) -> dict[tuple[int, int], int]:
    """Суммы по созданным (непринятым) перемещениям: склад-отправитель -> количество."""
    rows = db.execute(
        select(models.StockTransfer.from_warehouse_id, models.StockTransfer.sku_id, models.StockTransfer.quantity)
        .where(models.StockTransfer.status == "CREATED")
    ).all()
    result: dict[tuple[int, int], int] = {}
    for wh_id, sku_id, qty in rows:
        result[(wh_id, sku_id)] = result.get((wh_id, sku_id), 0) + qty
    return result


def list_stocks(db: Session) -> list[StockOut]:
    """Остатки по всем складам и товарам + три колонки 'в пути'."""
    ff = _transit_ff(db)
    out: list[StockOut] = []
    stocks = db.execute(
        select(models.Stock).join(models.Warehouse).join(models.Sku).order_by(models.Warehouse.name, models.Sku.code)
    ).scalars().all()
    for st in stocks:
        key = (st.warehouse_id, st.sku_id)
        shipped = db.execute(
            select(models.Reservation.quantity).where(
                models.Reservation.warehouse_id == st.warehouse_id,
                models.Reservation.sku_id == st.sku_id,
                models.Reservation.status == "SHIPPED",
            )
        ).scalars().all()
        fbo = db.execute(
            select(models.FboShipment.quantity).where(
                models.FboShipment.from_warehouse_id == st.warehouse_id,
                models.FboShipment.sku_id == st.sku_id,
                models.FboShipment.status == "IN_TRANSIT",
            )
        ).scalars().all()
        out.append(
            StockOut(
                id=st.id,
                warehouse_id=st.warehouse_id,
                warehouse_name=st.warehouse.name,
                is_active=st.warehouse.is_active,
                sku_code=st.sku.code,
                sku_name=st.sku.name,
                physical=st.physical,
                reserved=st.reserved,
                available=st.available,
                in_transit_ff=ff.get(key, 0),
                in_transit_fbo=sum(fbo),
                in_transit_client=sum(shipped),
            )
        )
    return out


def list_transfers(db: Session) -> list[TransferOut]:
    rows = db.execute(
        select(models.StockTransfer).order_by(models.StockTransfer.id.desc())
    ).scalars().all()
    out = []
    for tr in rows:
        sku = db.get(models.Sku, tr.sku_id)
        out.append(
            TransferOut(
                id=tr.id,
                sku_code=sku.code,
                from_name=db.get(models.Warehouse, tr.from_warehouse_id).name,
                to_name=db.get(models.Warehouse, tr.to_warehouse_id).name,
                quantity=tr.quantity,
                status=tr.status,
                created_at=tr.created_at,
                accepted_at=tr.accepted_at,
            )
        )
    return out


def list_reservations(db: Session) -> list[ReservationOut]:
    rows = db.execute(
        select(models.Reservation).order_by(models.Reservation.id.desc())
    ).scalars().all()
    out = []
    for r in rows:
        out.append(
            ReservationOut(
                id=r.id,
                warehouse_name=db.get(models.Warehouse, r.warehouse_id).name,
                sku_code=db.get(models.Sku, r.sku_id).code,
                quantity=r.quantity,
                status=r.status,
                created_at=r.created_at,
                shipped_at=r.shipped_at,
                cancelled_at=r.cancelled_at,
            )
        )
    return out


def list_fbo(db: Session) -> list[FboShipmentOut]:
    rows = db.execute(
        select(models.FboShipment).order_by(models.FboShipment.id.desc())
    ).scalars().all()
    out = []
    for sh in rows:
        out.append(
            FboShipmentOut(
                id=sh.id,
                from_name=db.get(models.Warehouse, sh.from_warehouse_id).name,
                sku_code=db.get(models.Sku, sh.sku_id).code,
                quantity=sh.quantity,
                status=sh.status,
                created_at=sh.created_at,
                received_at=sh.received_at,
            )
        )
    return out


def list_journal(db: Session) -> list[JournalOut]:
    rows = db.execute(
        select(models.OperationLog).order_by(models.OperationLog.id.desc())
    ).scalars().all()
    out = []
    for rec in rows:
        out.append(
            JournalOut(
                id=rec.id,
                ts=rec.ts,
                operation=rec.operation,
                sku_code=db.get(models.Sku, rec.sku_id).code if rec.sku_id else None,
                warehouse_name=db.get(models.Warehouse, rec.warehouse_id).name if rec.warehouse_id else None,
                quantity=rec.quantity,
                details=rec.details,
            )
        )
    return out
