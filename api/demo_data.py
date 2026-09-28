"""Small, clearly labelled records for the isolated Vue assignment database."""

from datetime import datetime, timezone
import sqlite3

from backend import database


def seed_assignment_examples() -> None:
    if not database.is_demo_mode_enabled():
        return
    with sqlite3.connect(database.DB_FILE) as conn:
        supplier = conn.execute(
            "SELECT supplier_id, country, region FROM suppliers "
            "WHERE risk_level = '高' AND COALESCE(country, '') != '' "
            "AND COALESCE(region, '') != '' ORDER BY supplier_id LIMIT 1"
        ).fetchone()
        if supplier is None:
            return
        supplier_id, country, region = supplier
        product = conn.execute(
            "SELECT product_id FROM inventory ORDER BY product_id LIMIT 1"
        ).fetchone()
        now = datetime.now(timezone.utc).isoformat()
        po_id = "VUE-DEMO-001"
        conn.execute(
            "INSERT OR IGNORE INTO purchase_orders "
            "(po_id, supplier_id, order_date, status, total_amount, note, "
            "estimated_delay_days, alternative_suggestion) "
            "VALUES (?, ?, ?, '處理中', 12000, ?, 5, ?)",
            (
                po_id, supplier_id, now[:10],
                "[作業版示範] 虛構採購單，僅供 Vue 篩選展示。",
                "[作業版示範] 請人工核對交期。",
            ),
        )
        if product is not None and not conn.execute(
            "SELECT 1 FROM purchase_order_items WHERE po_id = ?", (po_id,)
        ).fetchone():
            conn.execute(
                "INSERT INTO purchase_order_items (po_id, product_id, qty, unit_price) "
                "VALUES (?, ?, 10, 1200)", (po_id, product[0])
            )
        marker = "[作業版示範] 供應商所在地可能發生交期延遲。"
        if not conn.execute(
            "SELECT 1 FROM supply_chain_events WHERE description = ?", (marker,)
        ).fetchone():
            conn.execute(
                "INSERT INTO supply_chain_events "
                "(event_type, country, region, impact_days, description, created_at) "
                "VALUES ('示範事件', ?, ?, 5, ?, ?)",
                (country, region, marker, now),
            )
