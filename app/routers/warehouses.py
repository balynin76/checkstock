"""Роутер складов."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, services
from app.database import get_db
from app.schemas import WarehouseIn

router = APIRouter(prefix="/api/warehouses", tags=["warehouses"])


@router.get("")
def list_warehouses(db: Session = Depends(get_db)):
    rows = db.execute(select(models.Warehouse).order_by(models.Warehouse.id)).scalars().all()
    return [{"id": w.id, "name": w.name, "is_active": w.is_active} for w in rows]


@router.post("")
def create_warehouse(data: WarehouseIn, db: Session = Depends(get_db)):
    exists = db.execute(
        select(models.Warehouse).where(models.Warehouse.name == data.name)
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Склад с таким названием уже есть")
    wh = models.Warehouse(name=data.name)
    db.add(wh)
    db.commit()
    db.refresh(wh)
    return {"id": wh.id, "name": wh.name, "is_active": wh.is_active}


@router.delete("/{warehouse_id}")
def delete_warehouse(warehouse_id: int, db: Session = Depends(get_db)):
    services.soft_delete_warehouse(db, warehouse_id)
    return {"ok": True}
