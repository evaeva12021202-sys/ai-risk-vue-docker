"""Clearly labelled, idempotent records for the isolated Vue assignment database."""

from datetime import datetime, timezone
import sqlite3

from backend import database, supply_chain_risk


DEMO_RISK_BY_COUNTRY = {
    "墨西哥": 91,
    "德國": 82,
    "沙烏地阿拉伯": 73,
    "越南": 64,
    "阿拉伯聯合大公國": 54,
    "台灣": 43,
    "美國": 32,
    "日本": 18,
}


def seed_assignment_examples() -> None:
    if not database.is_demo_mode_enabled():
        return
    hotspots = sorted(
        supply_chain_risk.get_risk_heatmap_data(), key=lambda row: row["region_key"]
    )
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(database.DB_FILE) as conn:
        first = conn.execute(
            "SELECT s.supplier_id, s.country, s.region FROM purchase_orders p "
            "JOIN suppliers s ON s.supplier_id = p.supplier_id "
            "WHERE p.po_id = 'VUE-DEMO-001'"
        ).fetchone() or conn.execute(
            "SELECT supplier_id, country, region FROM suppliers "
            "WHERE is_official = 1 AND COALESCE(country, '') != '' "
            "AND COALESCE(region, '') != '' "
            "ORDER BY CASE WHEN risk_level = '高' THEN 0 ELSE 1 END, supplier_id LIMIT 1"
        ).fetchone()
        if first is None:
            return
        product = conn.execute(
            "SELECT product_id FROM inventory ORDER BY product_id LIMIT 1"
        ).fetchone()

        def add_order(po_id: str, supplier_id: str, delay: int, index: int) -> None:
            conn.execute(
                "INSERT OR IGNORE INTO purchase_orders "
                "(po_id, supplier_id, order_date, status, total_amount, note, "
                "estimated_delay_days, alternative_suggestion) "
                "VALUES (?, ?, ?, '處理中', ?, ?, ?, ?)",
                (
                    po_id, supplier_id, now[:10], 12000 + index * 1800,
                    "[作業版示範] 虛構採購單，僅供 Vue 篩選展示。",
                    delay, "[作業版示範] 請人工核對交期。",
                ),
            )
            if product is not None and not conn.execute(
                "SELECT 1 FROM purchase_order_items WHERE po_id = ?", (po_id,)
            ).fetchone():
                conn.execute(
                    "INSERT INTO purchase_order_items (po_id, product_id, qty, unit_price) "
                    "VALUES (?, ?, 10, 1200)", (po_id, product[0])
                )

        add_order("VUE-DEMO-001", first[0], 5, 0)
        marker = "[作業版示範] 供應商所在地可能發生交期延遲。"
        if not conn.execute(
            "SELECT 1 FROM supply_chain_events WHERE description = ?", (marker,)
        ).fetchone():
            conn.execute(
                "INSERT INTO supply_chain_events "
                "(event_type, country, region, impact_days, description, created_at) "
                "VALUES ('示範事件', ?, ?, 5, ?, ?)",
                (first[1], first[2], marker, now),
            )

        first_key = f"{first[1]}|{first[2]}"
        order_number = 2
        for hotspot in hotspots:
            region_key = hotspot["region_key"]
            country, region = region_key.split("|", 1)
            score = DEMO_RISK_BY_COUNTRY.get(country, 50)
            if region_key != first_key:
                supplier = conn.execute(
                    "SELECT supplier_id FROM suppliers WHERE country = ? AND region = ? "
                    "ORDER BY CASE WHEN risk_level = '高' THEN 0 ELSE 1 END, supplier_id LIMIT 1",
                    (country, region),
                ).fetchone()
                if supplier is not None:
                    add_order(
                        f"VUE-DEMO-{order_number:03d}", supplier[0],
                        max(1, round(score / 10)), order_number - 1,
                    )
                    order_number += 1
            conn.execute(
                "INSERT OR IGNORE INTO risk_heatmap "
                "(region_key, display_name, latitude, longitude, risk_pct, ai_summary, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    region_key, hotspot["display_name"], hotspot["latitude"],
                    hotspot["longitude"], score,
                    "[作業版示範] 虛構風險分數，用來展示各地區比較；不是 AI 即時判斷。",
                    now,
                ),
            )
