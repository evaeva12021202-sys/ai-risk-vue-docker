"""API-only ERP queries keep their datasets separate and role gated."""

import sqlite3

from fastapi.testclient import TestClient

from api.main import app
from api.read_only import RESOURCES
from backend import database, supply_chain_risk


def _login(client: TestClient, username: str) -> None:
    response = client.post(
        "/api/session", json={"username": username, "password": username}
    )
    assert response.status_code == 200


def test_every_allowlisted_dataset_is_readable_by_admin(tmp_path, monkeypatch):
    db_file = str(tmp_path / "api-only.db")
    monkeypatch.setenv("ERP_DEMO_MODE", "true")
    monkeypatch.setattr(database, "DB_FILE", db_file)
    monkeypatch.setattr(supply_chain_risk, "DB_FILE", db_file)

    with TestClient(app) as client:
        assert client.get("/api/data").status_code == 401
        _login(client, "admin")
        catalog = client.get("/api/data")
        assert catalog.status_code == 200
        keys = {resource["key"] for resource in catalog.json()["resources"]}
        assert keys == set(RESOURCES)
        for key in keys:
            response = client.get(f"/api/data/{key}?limit=1")
            assert response.status_code == 200, (key, response.text)
            body = response.json()
            assert body["resource"] == key
            assert body["columns"]
            assert len(body["items"]) <= 1
        assert client.get("/api/data/unknown").status_code == 404
        assert client.get("/api/data/inventory/products?limit=101").status_code == 422
        assert client.get("/api/data/inventory/products?offset=-1").status_code == 422
        assert client.post("/api/data/inventory/products").status_code == 405


def test_role_boundaries_and_live_authorization(tmp_path, monkeypatch):
    db_file = str(tmp_path / "api-roles.db")
    monkeypatch.setenv("ERP_DEMO_MODE", "true")
    monkeypatch.setattr(database, "DB_FILE", db_file)
    monkeypatch.setattr(supply_chain_risk, "DB_FILE", db_file)

    with TestClient(app) as viewer:
        _login(viewer, "viewer")
        assert viewer.get("/api/data/risk/events").status_code == 200
        assert viewer.get("/api/data/hr/payroll").status_code == 403
        assert viewer.get("/api/data/finance/ledger").status_code == 403
        assert viewer.get("/api/data/sales/customers").status_code == 403
        assert {item["module"] for item in viewer.get("/api/data").json()["resources"]} == {"risk"}
        with sqlite3.connect(db_file) as conn:
            conn.execute(
                "UPDATE organization_entitlements SET enabled = 0 "
                "WHERE organization_id = 'demo-org' AND entitlement_key = 'l1_monitor'"
            )
        assert viewer.get("/api/data/risk/events").status_code == 403

    with TestClient(app) as sales:
        _login(sales, "sales1")
        assert sales.get("/api/data/sales/orders").status_code == 200
        assert sales.get("/api/data/carbon/factors").status_code == 200
        assert sales.get("/api/data/hr/employees").status_code == 403
        assert sales.get("/api/data/finance/ledger").status_code == 403
        with sqlite3.connect(db_file) as conn:
            conn.execute("UPDATE users SET role = 'risk_viewer' WHERE username = 'sales1'")
        assert sales.get("/api/data/sales/orders").status_code == 403

    with TestClient(app) as hr:
        _login(hr, "hr1")
        assert hr.get("/api/data/hr/payroll").status_code == 200
        assert hr.get("/api/data/sales/customers").status_code == 403

    with TestClient(app) as warehouse:
        _login(warehouse, "wh1")
        assert warehouse.get("/api/data/inventory/products").status_code == 200
        assert warehouse.get("/api/data/procurement/suppliers").status_code == 200
        assert warehouse.get("/api/data/hr/payroll").status_code == 403
