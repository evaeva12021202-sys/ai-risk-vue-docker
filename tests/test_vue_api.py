"""The Vue API must use its own database and recheck ERP authorization."""

import sqlite3

from fastapi.testclient import TestClient

from api.main import app
from backend import database, supply_chain_risk


def test_vue_login_and_overview_respect_live_entitlements(tmp_path, monkeypatch):
    db_file = str(tmp_path / "vue-demo.db")
    monkeypatch.setenv("ERP_DEMO_MODE", "true")
    monkeypatch.setattr(database, "DB_FILE", db_file)
    monkeypatch.setattr(supply_chain_risk, "DB_FILE", db_file)

    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        assert client.get("/api/overview").status_code == 401
        assert client.post(
            "/api/session", json={"username": "viewer", "password": "wrong"}
        ).status_code == 401

        login = client.post(
            "/api/session", json={"username": "viewer", "password": "viewer"}
        )
        assert login.status_code == 200
        assert login.json()["role"] == "risk_viewer"
        assert "httponly" in login.headers["set-cookie"].lower()
        overview = client.get("/api/overview")
        assert overview.status_code == 200
        assert set(overview.json()) == {
            "generated_at", "kpis", "regions", "events", "high_risk_suppliers"
        }
        assert overview.json()["regions"]

        with sqlite3.connect(db_file) as conn:
            conn.execute(
                "UPDATE organization_entitlements SET enabled = 0 "
                "WHERE organization_id = 'demo-org' AND entitlement_key = 'l1_monitor'"
            )
        assert client.get("/api/overview").status_code == 403
        assert client.delete("/api/session").status_code == 204
        assert client.get("/api/overview").status_code == 401
