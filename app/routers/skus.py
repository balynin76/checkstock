"""Роутер товаров."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.schemas import SkuIn

router = APIRouter(prefix="/api/skus", tags=["skus"])


@router.get("")
def list_skus(db: Session = Depends(get_db)):
    rows = db.execute(select(models.Sku).order_by(models.Sku.code)).scalars().all()
    return [{"id": s.id, "code": s.code, "name": s.name} for s in rows]


@router.post("")
def create_sku(data: SkuIn, db: Session = Depends(get_db)):
    exists = db.execute(select(models.Sku).where(models.Sku.code == data.code)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Артикул уже существует")
    sku = models.Sku(code=data.code, name=data.name)
    db.add(sku)
    db.commit()
    db.refresh(sku)
    return {"id": sku.id, "code": sku.code, "name": sku.name}
