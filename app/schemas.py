"""Pydantic-схемы запросов и ответов."""
from datetime import datetime

from pydantic import BaseModel, Field


class WarehouseIn(BaseModel):
    name: str = Field(min_length=1)


class SkuIn(BaseModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)


class ReceiptIn(BaseModel):
    warehouse_id: int
    sku_id: int
    quantity: int = Field(gt=0)


class TransferIn(BaseModel):
    from_warehouse_id: int
    to_warehouse_id: int
    sku_id: int
    quantity: int = Field(gt=0)


class ReservationIn(BaseModel):
    warehouse_id: int
    sku_id: int
    quantity: int = Field(gt=0)


class FboShipmentIn(BaseModel):
    warehouse_id: int
    sku_id: int
    quantity: int = Field(gt=0)


class StockOut(BaseModel):
    id: int
    warehouse_id: int
    warehouse_name: str
    is_active: bool
    sku_code: str
    sku_name: str
    physical: int
    reserved: int
    available: int
    in_transit_ff: int
    in_transit_fbo: int
    in_transit_client: int


class TransferOut(BaseModel):
    id: int
    sku_code: str
    from_name: str
    to_name: str
    quantity: int
    status: str
    created_at: datetime
    accepted_at: datetime | None = None


class ReservationOut(BaseModel):
    id: int
    warehouse_name: str
    sku_code: str
    quantity: int
    status: str
    created_at: datetime
    shipped_at: datetime | None = None
    cancelled_at: datetime | None = None


class FboShipmentOut(BaseModel):
    id: int
    from_name: str
    sku_code: str
    quantity: int
    status: str
    created_at: datetime
    received_at: datetime | None = None


class JournalOut(BaseModel):
    id: int
    ts: datetime
    operation: str
    sku_code: str | None = None
    warehouse_name: str | None = None
    quantity: int
    details: str
