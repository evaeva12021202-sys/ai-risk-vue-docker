"""The Vue API must use its own database and recheck ERP authorization."""

import sqlite3
from urllib.parse import quote

from fastapi.testclient import TestClient

from api.main import app
from api.demo_data import seed_assignment_examples
from backend import database, supply_chain_risk


def test_vue_login_and_overview_respect_live_entitlements(tmp_path, monkeypatch):
    db_file = str(tmp_path / "vue-demo.db")
    monkeypatch.setenv("ERP_DEMO_MODE", "true")
    monkeypatch.setattr(database, "DB_FILE", db_file)
    monkeypatch.setattr(supply_chain_risk, "DB_FILE", db_file)

    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        assert client.get("/api/overview").status_code == 401
        assert client.get("/api/regions/demo%7Cdemo/details").status_code == 401
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
            "generated_at", "demo_mode", "kpis", "regions", "events", "high_risk_suppliers"
        }
        assert overview.json()["demo_mode"] is True
        assert overview.json()["regions"]
        scores = [region["risk_pct"] for region in overview.json()["regions"]]
        assert max(scores) - min(scores) >= 50
        for region in overview.json()["regions"]:
            regional_details = client.get(
                f"/api/regions/{quote(region['region_key'], safe='')}/details"
            )
            assert regional_details.status_code == 200
            assert any(
                order["po_id"].startswith("VUE-DEMO-")
                for order in regional_details.json()["open_purchase_orders"]
            )

        with sqlite3.connect(db_file) as conn:
            supplier = conn.execute(
                "SELECT s.supplier_id, s.country, s.region FROM purchase_orders p "
                "JOIN suppliers s ON s.supplier_id = p.supplier_id "
                "WHERE p.po_id = 'VUE-DEMO-001'"
            ).fetchone()
        assert supplier is not None
        region_key = f"{supplier[1]}|{supplier[2]}"
        detail_path = f"/api/regions/{quote(region_key, safe='')}/details"
        details = client.get(detail_path)
        assert details.status_code == 200
        assert details.json()["region_key"] == region_key
        assert any(s["supplier_id"] == supplier[0] for s in details.json()["suppliers"])
        assert any(
            p["po_id"] == "VUE-DEMO-001" and p["supplier_name"] and p["items"]
            for p in details.json()["open_purchase_orders"]
        )
        assert any("[作業版示範]" in (e["description"] or "") for e in details.json()["events"])
        other_region = next(
            r["region_key"] for r in overview.json()["regions"]
            if r["region_key"] != region_key
        )
        other_details = client.get(
            f"/api/regions/{quote(other_region, safe='')}/details"
        )
        assert other_details.status_code == 200
        assert all(p["po_id"] != "VUE-DEMO-001" for p in other_details.json()["open_purchase_orders"])
        assert client.get("/api/regions/not-found/details").status_code == 404
        seed_assignment_examples()
        with sqlite3.connect(db_file) as conn:
            assert conn.execute(
                "SELECT COUNT(*) FROM purchase_orders WHERE po_id LIKE 'VUE-DEMO-%'"
            ).fetchone()[0] == len(overview.json()["regions"])
            assert conn.execute(
                "SELECT COUNT(*) FROM purchase_orders WHERE po_id = 'VUE-DEMO-001'"
            ).fetchone()[0] == 1
            assert conn.execute(
                "SELECT COUNT(*) FROM supply_chain_events "
                "WHERE description LIKE '[作業版示範]%'").fetchone()[0] == 1

        with sqlite3.connect(db_file) as conn:
            conn.execute(
                "UPDATE risk_heatmap SET risk_pct = 7 WHERE region_key = ?",
                (region_key,),
            )
        seed_assignment_examples()
        with sqlite3.connect(db_file) as conn:
            assert conn.execute(
                "SELECT risk_pct FROM risk_heatmap WHERE region_key = ?",
                (region_key,),
            ).fetchone()[0] == 7
            conn.execute(
                "UPDATE organization_entitlements SET enabled = 0 "
                "WHERE organization_id = 'demo-org' AND entitlement_key = 'l1_monitor'"
            )
        assert client.get("/api/overview").status_code == 403
        assert client.get(detail_path).status_code == 403
        assert client.delete("/api/session").status_code == 204
        assert client.get("/api/overview").status_code == 401


def test_assignment_example_seed_is_disabled_outside_demo_mode(tmp_path, monkeypatch):
    db_file = tmp_path / "non-demo.db"
    monkeypatch.setenv("ERP_DEMO_MODE", "false")
    monkeypatch.setattr(database, "DB_FILE", str(db_file))
    seed_assignment_examples()
    assert not db_file.exists()
