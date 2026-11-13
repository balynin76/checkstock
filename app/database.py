"""Подключение к БД. SQLite по умолчанию, Postgres через переменную окружения."""
import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./checkstock.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# Для кода приложения (seed, стартовые задачи) — та же фабрика под историческим именем
SessionLocal = TestSession


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = TestSession()
    try:
        yield db
    finally:
        db.close()
