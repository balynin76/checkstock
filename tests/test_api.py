"""Автотесты ключевых сценариев CheckStock."""
from app.database import TestSession


def _db():
    return TestSession()


def test_seed_stocks(client):
    stocks = client.get("/api/stocks").json()
    data = {(s["warehouse_name"], s["sku_code"]): s for s in stocks}
    assert data[("Север", "SKU-101")]["physical"] == 5
    assert data[("Юг", "SKU-101")]["physical"] == 0
    assert data[("Север", "SKU-101")]["available"] == 5


def test_receipt_increases_stock(client):
    south_id = _wh_id(client, "Юг")
    sku_id = _sku_id(client, "SKU-101")
    client.post("/api/receipts", json={"warehouse_id": south_id, "sku_id": sku_id, "quantity": 7})
    row = _stock(client, "Юг", "SKU-101")
    assert row["physical"] == 7
    assert row["available"] == 7


def test_transfer_cycle(client):
    north_id, south_id = _wh_id(client, "Север"), _wh_id(client, "Юг")
    sku_id = _sku_id(client, "SKU-101")
    r = client.post("/api/transfers",
                    json={"from_warehouse_id": north_id, "to_warehouse_id": south_id, "sku_id": sku_id, "quantity": 3})
    assert r.status_code == 200
    row = _stock(client, "Север", "SKU-101")
    assert row["physical"] == 2
    assert row["in_transit_ff"] == 3
    assert _stock(client, "Юг", "SKU-101")["physical"] == 0
    transfer_id = r.json()["id"]
    r = client.post(f"/api/transfers/{transfer_id}/accept")
    assert r.status_code == 200
    assert _stock(client, "Юг", "SKU-101")["physical"] == 3
    assert _stock(client, "Север", "SKU-101")["in_transit_ff"] == 0


def test_double_accept_returns_409(client):
    north_id, south_id = _wh_id(client, "Север"), _wh_id(client, "Юг")
    sku_id = _sku_id(client, "SKU-101")
    transfer_id = client.post("/api/transfers", json={
        "from_warehouse_id": north_id, "to_warehouse_id": south_id, "sku_id": sku_id, "quantity": 1,
    }).json()["id"]
    assert client.post(f"/api/transfers/{transfer_id}/accept").status_code == 200
    r = client.post(f"/api/transfers/{transfer_id}/accept")
    assert r.status_code == 409
    assert _stock(client, "Юг", "SKU-101")["physical"] == 1  # товар не списан дважды


def test_shortage_hint_points_to_other_warehouse(client):
    south_id = _wh_id(client, "Юг")
    sku_id = _sku_id(client, "SKU-101")
    r = client.post("/api/transfers",
                    json={"from_warehouse_id": south_id, "to_warehouse_id": _wh_id(client, "Север"),
                          "sku_id": sku_id, "quantity": 10})
    assert r.status_code == 409
    assert "Север" in r.json()["detail"]
    assert "5" in r.json()["detail"]


def test_reservation_ship_cancel_cycle(client):
    north_id = _wh_id(client, "Север")
    sku_id = _sku_id(client, "SKU-102")
    # резерв: available падает, physical не трогается
    r = client.post("/api/reservations", json={"warehouse_id": north_id, "sku_id": sku_id, "quantity": 4})
    assert r.status_code == 200
    res_id = r.json()["id"]
    assert _stock(client, "Север", "SKU-102")["available"] == 6
    assert _stock(client, "Север", "SKU-102")["physical"] == 10
    # отмена: бронь снимается
    r = client.post(f"/api/reservations/{res_id}/cancel")
    assert r.status_code == 200
    assert _stock(client, "Север", "SKU-102")["available"] == 10
    # повторный резерв и отгрузка
    res_id = client.post("/api/reservations",
                         json={"warehouse_id": north_id, "sku_id": sku_id, "quantity": 4}).json()["id"]
    r = client.post(f"/api/reservations/{res_id}/ship")
    assert r.status_code == 200
    assert _stock(client, "Север", "SKU-102")["physical"] == 6
    assert _stock(client, "Север", "SKU-102")["in_transit_client"] == 4
    # повторная отгрузка — 409
    r = client.post(f"/api/reservations/{res_id}/ship")
    assert r.status_code == 409
    # отмена после отгрузки — 409
    r = client.post(f"/api/reservations/{res_id}/cancel")
    assert r.status_code == 409


def test_fbo_cycle(client):
    north_id = _wh_id(client, "Север")
    sku_id = _sku_id(client, "SKU-103")
    r = client.post("/api/fbo-shipments", json={"warehouse_id": north_id, "sku_id": sku_id, "quantity": 2})
    assert r.status_code == 200
    sh_id = r.json()["id"]
    row = _stock(client, "Север", "SKU-103")
    assert row["physical"] == 1
    assert row["in_transit_fbo"] == 2
    r = client.post(f"/api/fbo-shipments/{sh_id}/accept")
    assert r.status_code == 200
    assert _stock(client, "Север", "SKU-103")["in_transit_fbo"] == 0
    r = client.post(f"/api/fbo-shipments/{sh_id}/accept")
    assert r.status_code == 409


def test_soft_delete_preserves_stock_and_journal(client):
    north_id = _wh_id(client, "Север")
    before = len(client.get("/api/journal").json())
    r = client.delete(f"/api/warehouses/{north_id}")
    assert r.status_code == 200
    row = _stock(client, "Север", "SKU-101")
    assert row["physical"] == 5          # остатки сохранены
    assert row["is_active"] is False     # склад помечен неактивным
    after = client.get("/api/journal").json()
    assert len(after) == before + 1      # запись в журнале добавлена
    assert after[0]["operation"] == "УДАЛЕНИЕ СКЛАДА"


def _wh_id(client, name):
    return next(w["id"] for w in client.get("/api/warehouses").json() if w["name"] == name)


def _sku_id(client, code):
    return next(s["id"] for s in client.get("/api/skus").json() if s["code"] == code)


def _stock(client, wh_name, sku_code):
    stocks = client.get("/api/stocks").json()
    return next(s for s in stocks if s["warehouse_name"] == wh_name and s["sku_code"] == sku_code)
