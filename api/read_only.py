"""Allowlisted, paginated ERP queries for the API-only migration stage.

No request parameter can become SQL or a table name. All role checks use the
principal freshly loaded by the API on every request.
"""

from dataclasses import dataclass
import sqlite3

from backend import database
from backend.access_control import RISK_OVERVIEW_READ, AccessContext


@dataclass(frozen=True)
class Resource:
    module: str
    label: str
    roles: frozenset[str]
    sql: str
    capability: str | None = None


def _resource(module: str, label: str, roles: str, sql: str) -> Resource:
    return Resource(module, label, frozenset(roles.split()), sql)


RESOURCES: dict[str, Resource] = {
    "dashboard": _resource(
        "dashboard", "營運指標", "admin warehouse sales hr",
        "SELECT (SELECT COALESCE(SUM(stock * COALESCE(cost, 0)), 0) FROM inventory) AS inventory_value, "
        "(SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status != '已取消' "
        "AND strftime('%Y-%m', order_date) = strftime('%Y-%m','now')) AS month_revenue, "
        "(SELECT COUNT(*) FROM orders WHERE status != '已取消' "
        "AND strftime('%Y-%m', order_date) = strftime('%Y-%m','now')) AS month_orders, "
        "(SELECT COUNT(*) FROM inventory WHERE reorder_point > 0 "
        "AND stock <= reorder_point) AS low_stock_count",
    ),
    "inventory/products": _resource(
        "inventory", "商品與庫存", "admin warehouse",
        "SELECT product_id, name, stock, price, cost, reorder_point, "
        "baseline_reorder_point, daily_sales, barcode, warehouse_id "
        "FROM inventory ORDER BY product_id",
    ),
    "inventory/warehouses": _resource(
        "inventory", "倉庫", "admin warehouse",
        "SELECT warehouse_id, name, address FROM warehouses ORDER BY warehouse_id",
    ),
    "inventory/stock-moves": _resource(
        "inventory", "出入庫記錄", "admin warehouse",
        "SELECT move_id, product_id, warehouse_id, qty, move_type, ref_no, "
        "move_date, note FROM stock_moves ORDER BY move_id DESC",
    ),
    "inventory/bom": _resource(
        "inventory", "物料清單", "admin warehouse",
        "SELECT id, product_id, component_id, qty_per FROM bom ORDER BY id DESC",
    ),
    "inventory/work-orders": _resource(
        "inventory", "製造工單", "admin warehouse",
        "SELECT wo_id, product_id, qty_plan, qty_done, status, start_date, end_date "
        "FROM work_orders ORDER BY start_date DESC, wo_id DESC",
    ),
    "procurement/suppliers": _resource(
        "procurement", "供應商", "admin warehouse",
        "SELECT supplier_id, name, contact, phone, email, country, region, "
        "risk_level, is_official FROM suppliers ORDER BY supplier_id",
    ),
    "procurement/purchase-orders": _resource(
        "procurement", "採購單", "admin warehouse",
        "SELECT p.po_id, p.supplier_id, s.name AS supplier_name, p.order_date, "
        "p.status, p.total_amount, p.estimated_delay_days "
        "FROM purchase_orders p LEFT JOIN suppliers s ON s.supplier_id = p.supplier_id "
        "ORDER BY p.order_date DESC, p.po_id DESC",
    ),
    "procurement/purchase-order-items": _resource(
        "procurement", "採購明細", "admin warehouse",
        "SELECT id, po_id, product_id, qty, unit_price FROM purchase_order_items ORDER BY id DESC",
    ),
    "sales/customers": _resource(
        "sales", "客戶", "admin sales",
        "SELECT customer_id, name, company, contact, phone, email, country, region "
        "FROM customers ORDER BY customer_id",
    ),
    "sales/quotations": _resource(
        "sales", "報價單", "admin sales",
        "SELECT quote_id, customer_id, quote_date, status, total_amount, valid_until "
        "FROM quotations ORDER BY quote_date DESC, quote_id DESC",
    ),
    "sales/quotation-items": _resource(
        "sales", "報價明細", "admin sales",
        "SELECT id, quote_id, product_id, qty, unit_price "
        "FROM quotation_items ORDER BY id DESC",
    ),
    "sales/orders": _resource(
        "sales", "銷售單", "admin sales",
        "SELECT order_id, customer_id, product_id, quantity, status, order_date, "
        "total_amount FROM orders ORDER BY order_date DESC, order_id DESC",
    ),
    "sales/payments": _resource(
        "sales", "收款", "admin sales",
        "SELECT payment_id, ref_type, ref_id, amount, payment_date, note "
        "FROM payments ORDER BY payment_id DESC",
    ),
    "finance/receivables": _resource(
        "finance", "應收帳款", "admin",
        "SELECT id, customer_id, ref_id, amount, paid, due_date "
        "FROM receivables ORDER BY id DESC",
    ),
    "finance/payables": _resource(
        "finance", "應付帳款", "admin",
        "SELECT id, supplier_id, ref_id, amount, paid, due_date "
        "FROM payables ORDER BY id DESC",
    ),
    "finance/ledger": _resource(
        "finance", "總帳", "admin",
        "SELECT id, ledger_date, account, debit, credit, description "
        "FROM general_ledger ORDER BY id DESC",
    ),
    "finance/costs": _resource(
        "finance", "成本分析", "admin",
        "SELECT product_id, name, stock, cost, price, "
        "stock * COALESCE(cost, 0) AS stock_cost "
        "FROM inventory ORDER BY product_id",
    ),
    "hr/employees": _resource(
        "hr", "員工資料", "admin hr",
        "SELECT employee_id, name, department, role, salary FROM hr ORDER BY employee_id",
    ),
    "hr/payroll": _resource(
        "hr", "薪資", "admin hr",
        "SELECT id, employee_id, period, base_salary, bonus, deduction, "
        "base_salary + bonus - deduction AS net_salary "
        "FROM payroll ORDER BY period DESC, id DESC",
    ),
    "hr/attendance": _resource(
        "hr", "出勤", "admin hr",
        "SELECT id, employee_id, work_date, check_in, check_out, status "
        "FROM attendance ORDER BY work_date DESC, id DESC",
    ),
    "carbon/factors": _resource(
        "carbon", "碳排係數", "admin sales",
        "SELECT id, product_id, scope, kg_co2_per_unit, note "
        "FROM carbon_factors ORDER BY product_id, scope",
    ),
    "carbon/targets": _resource(
        "carbon", "減量目標", "admin",
        "SELECT id, target_year, scope, baseline_kg_co2, target_kg_co2, note "
        "FROM esg_targets ORDER BY target_year DESC, scope",
    ),
    "carbon/emissions": _resource(
        "carbon", "每月碳排", "admin sales",
        "SELECT strftime('%Y-%m', o.order_date) AS period, cf.scope, "
        "SUM(o.quantity * cf.kg_co2_per_unit) AS kg_co2e "
        "FROM orders o JOIN carbon_factors cf ON cf.product_id = o.product_id "
        "WHERE o.status != '已取消' "
        "GROUP BY period, cf.scope ORDER BY period DESC, cf.scope",
    ),
    "ai/line-logs": _resource(
        "ai", "LINE 客服記錄", "admin",
        "SELECT id, user_id, user_name, user_msg, ai_reply, created_at "
        "FROM line_bot_logs ORDER BY id DESC",
    ),
    "ai/agent-actions": _resource(
        "ai", "Agent 動作記錄", "admin",
        "SELECT id, tool_name, caller, success, timestamp, checksum "
        "FROM agent_action_logs ORDER BY id DESC",
    ),
    "risk/events": Resource(
        "risk", "供應鏈風險事件", frozenset(),
        "SELECT id, event_type, country, region, impact_days, description, created_at "
        "FROM supply_chain_events ORDER BY id DESC", RISK_OVERVIEW_READ,
    ),
    "risk/news": Resource(
        "risk", "供應鏈新聞", frozenset(),
        "SELECT id, country, region, title, summary, url, source, published_at "
        "FROM supply_chain_news ORDER BY id DESC", RISK_OVERVIEW_READ,
    ),
}


def can_read(principal: AccessContext, resource: Resource) -> bool:
    if resource.capability:
        return principal.can(resource.capability)
    return principal.role in resource.roles


def list_resources(principal: AccessContext) -> list[dict[str, str]]:
    return [
        {"key": key, "module": resource.module, "label": resource.label}
        for key, resource in RESOURCES.items()
        if can_read(principal, resource)
    ]


def read_resource(resource: Resource, limit: int, offset: int) -> tuple[list[str], list[dict], bool]:
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
        cursor = conn.execute(
            f"SELECT * FROM ({resource.sql}) LIMIT ? OFFSET ?", (limit + 1, offset)
        )
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
    return columns, [dict(row) for row in rows[:limit]], len(rows) > limit
