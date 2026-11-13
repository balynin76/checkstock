"""Сидирование демо-данных при первом запуске."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


def seed(db: Session) -> None:
    if db.execute(select(models.Warehouse).limit(1)).scalar_one_or_none() is not None:
        return
    north = models.Warehouse(name="Север")
    south = models.Warehouse(name="Юг")
    db.add_all([north, south])
    db.flush()
    skus = [
        models.Sku(code="SKU-101", name="Органайзер настольный"),
        models.Sku(code="SKU-102", name="Контейнер для хранения"),
        models.Sku(code="SKU-103", name="Полка навесная"),
    ]
    db.add_all(skus)
    db.flush()
    demo = [
        (north, skus[0], 5),   # SKU-101 на Севере: 5 шт. — подсказка при нехватке на Юге
        (south, skus[0], 0),   # SKU-101 на Юге: 0 — для демонстрации нехватки
        (north, skus[1], 10),
        (south, skus[1], 8),
        (north, skus[2], 3),
        (south, skus[2], 12),
    ]
    for wh, sku, qty in demo:
        db.add(models.Stock(warehouse_id=wh.id, sku_id=sku.id, physical=qty, reserved=0))
    db.commit()
