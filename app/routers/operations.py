"""Роутер операций: приход, перемещения, резервы FBS, отправки FBO."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas, services
from app.database import get_db
from app.queries import list_fbo, list_reservations, list_transfers

router = APIRouter(tags=["operations"])


@router.post("/api/receipts")
def receipt(data: schemas.ReceiptIn, db: Session = Depends(get_db)):
    stock = services.receive_stock(db, warehouse_id=data.warehouse_id, sku_id=data.sku_id, quantity=data.quantity)
    return {"ok": True, "physical": stock.physical, "available": stock.available}


@router.get("/api/transfers")
def transfers(db: Session = Depends(get_db)):
    return list_transfers(db)


@router.post("/api/transfers")
def create_transfer(data: schemas.TransferIn, db: Session = Depends(get_db)):
    tr = services.create_transfer(
        db,
        from_warehouse_id=data.from_warehouse_id,
        to_warehouse_id=data.to_warehouse_id,
        sku_id=data.sku_id,
        quantity=data.quantity,
    )
    return {"ok": True, "id": tr.id, "status": tr.status}


@router.post("/api/transfers/{transfer_id}/accept")
def accept_transfer(transfer_id: int, db: Session = Depends(get_db)):
    tr = services.accept_transfer(db, transfer_id)
    return {"ok": True, "id": tr.id, "status": tr.status}


@router.get("/api/reservations")
def reservations(db: Session = Depends(get_db)):
    return list_reservations(db)


@router.post("/api/reservations")
def create_reservation(data: schemas.ReservationIn, db: Session = Depends(get_db)):
    r = services.create_reservation(db, warehouse_id=data.warehouse_id, sku_id=data.sku_id, quantity=data.quantity)
    return {"ok": True, "id": r.id, "status": r.status}


@router.post("/api/reservations/{reservation_id}/ship")
def ship_reservation(reservation_id: int, db: Session = Depends(get_db)):
    r = services.ship_reservation(db, reservation_id)
    return {"ok": True, "id": r.id, "status": r.status}


@router.post("/api/reservations/{reservation_id}/cancel")
def cancel_reservation(reservation_id: int, db: Session = Depends(get_db)):
    r = services.cancel_reservation(db, reservation_id)
    return {"ok": True, "id": r.id, "status": r.status}


@router.get("/api/fbo-shipments")
def fbo_shipments(db: Session = Depends(get_db)):
    return list_fbo(db)


@router.post("/api/fbo-shipments")
def create_fbo_shipment(data: schemas.FboShipmentIn, db: Session = Depends(get_db)):
    sh = services.create_fbo_shipment(db, warehouse_id=data.warehouse_id, sku_id=data.sku_id, quantity=data.quantity)
    return {"ok": True, "id": sh.id, "status": sh.status}


@router.post("/api/fbo-shipments/{shipment_id}/accept")
def accept_fbo(shipment_id: int, db: Session = Depends(get_db)):
    sh = services.receive_fbo(db, shipment_id)
    return {"ok": True, "id": sh.id, "status": sh.status}
