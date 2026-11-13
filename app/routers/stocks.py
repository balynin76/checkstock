"""Роутер остатков."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.queries import list_stocks

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("")
def stocks(db: Session = Depends(get_db)):
    return list_stocks(db)
