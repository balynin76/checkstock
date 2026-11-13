"""Роутер журнала (append-only)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.queries import list_journal

router = APIRouter(prefix="/api/journal", tags=["journal"])


@router.get("")
def journal(db: Session = Depends(get_db)):
    return list_journal(db)
