"""Точка входа FastAPI: роутеры, сидирование, раздача интерфейса."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app import seed
from app.database import SessionLocal, engine
from app.models import Base
from app.routers import journal, operations, skus, stocks, warehouses

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        seed.seed(db)
    finally:
        db.close()
    yield


app = FastAPI(title="CheckStock", lifespan=lifespan)

app.include_router(warehouses.router)
app.include_router(skus.router)
app.include_router(stocks.router)
app.include_router(operations.router)
app.include_router(journal.router)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")
