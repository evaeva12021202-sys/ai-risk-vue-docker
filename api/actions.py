"""Allowlisted ERP commands for the independent local Vue workspace.

The public LAN proxy never forwards these routes. Table and column names come
only from the definitions below; request data is always bound as parameters.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import sqlite3

from fastapi import HTTPException

from backend import database
from backend.access_control import AccessContext, RISK_WORKSPACE_WRITE


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    kind: str = "text"
    required: bool = True
    minimum: float | None = None


@dataclass(frozen=True)
class Action:
    label: str
    module: str
    roles: frozenset[str]
    fields: tuple[Field, ...]
    table: str | None = None
    capability: str | None = None


def f(key: str, label: str, kind: str = "text", required: bool = True,
      minimum: float | None = None) -> Field:
    return Field(key, label, kind, required, minimum)


ACTIONS: dict[str, Action] = {
    "inventory/product": Action("新增商品", "inventory", frozenset({"admin", "warehouse"}), (
        f("product_id", "產品編號"), f("name", "產品名稱"), f("stock", "初始庫存", "integer", minimum=0),
        f("price", "售價", "number", minimum=0), f("cost", "成本", "number", minimum=0),
        f("reorder_point", "安全庫存", "integer", minimum=0), f("daily_sales", "日均銷量", "integer", minimum=0),
        f("barcode", "條碼", required=False), f("warehouse_id", "倉庫代號", required=False)), "inventory"),
    "inventory/warehouse": Action("新增倉庫", "inventory", frozenset({"admin", "warehouse"}), (
        f("warehouse_id", "倉庫代號"), f("name", "倉庫名稱"), f("address", "地址", required=False)), "warehouses"),
    "inventory/stock-move": Action("入庫／出庫", "inventory", frozenset({"admin", "warehouse"}), (
        f("product_id", "產品編號"), f("move_type", "類型：入庫或出庫"),
        f("qty", "數量", "integer", minimum=1), f("ref_no", "單據編號", required=False),
        f("note", "備註", required=False))),
    "procurement/supplier": Action("新增供應商", "procurement", frozenset({"admin", "warehouse"}), (
        f("supplier_id", "供應商代號"), f("name", "公司名稱"), f("contact", "聯絡人", required=False),
        f("phone", "電話", required=False), f("email", "Email", required=False),
        f("country", "國家", required=False), f("region", "地區", required=False),
        f("risk_level", "風險等級：低、中或高", required=False)), "suppliers"),
    "sales/quotation": Action("建立報價單", "sales", frozenset({"admin", "sales"}), (
        f("quote_id", "報價單號"), f("customer_id", "客戶代號"), f("product_id", "產品編號"),
        f("qty", "數量", "integer", minimum=1), f("unit_price", "單價", "number", minimum=0),
        f("valid_until", "有效期限", "date"))),
    "sales/order": Action("建立銷售單", "sales", frozenset({"admin", "sales"}), (
        f("order_id", "訂單編號"), f("customer_id", "客戶代號"), f("product_id", "產品編號"),
        f("quantity", "數量", "integer", minimum=1))),
    "sales/order-status": Action("更新訂單狀態", "sales", frozenset({"admin", "sales"}), (
        f("order_id", "訂單編號"), f("status", "新狀態：處理中、已出貨或已取消"))),
    "sales/payment": Action("新增收款", "sales", frozenset({"admin", "sales"}), (
        f("ref_type", "單據類型"), f("ref_id", "單據編號"), f("amount", "金額", "number", minimum=0.01),
        f("payment_date", "收款日期", "date"), f("note", "備註", required=False)), "payments"),
    "finance/ledger": Action("新增總帳分錄", "finance", frozenset({"admin"}), (
        f("ledger_date", "日期", "date"), f("account", "會計科目"),
        f("debit", "借方", "number", minimum=0), f("credit", "貸方", "number", minimum=0),
        f("description", "說明", required=False)), "general_ledger"),
    "hr/employee": Action("新增員工", "hr", frozenset({"admin", "hr"}), (
        f("employee_id", "員工編號"), f("name", "姓名"), f("department", "部門", required=False),
        f("role", "職位", required=False), f("salary", "月薪", "number", minimum=0)), "hr"),
    "hr/payroll": Action("登錄薪資", "hr", frozenset({"admin", "hr"}), (
        f("employee_id", "員工編號"), f("period", "月份 YYYY-MM"),
        f("base_salary", "本薪", "number", minimum=0), f("bonus", "獎金", "number", minimum=0),
        f("deduction", "扣款", "number", minimum=0)), "payroll"),
    "hr/attendance": Action("登記出勤", "hr", frozenset({"admin", "hr"}), (
        f("employee_id", "員工編號"), f("work_date", "日期", "date"),
        f("check_in", "上班時間"), f("check_out", "下班時間"), f("status", "狀態")), "attendance"),
    "carbon/factor": Action("新增碳排係數", "carbon", frozenset({"admin", "sales"}), (
        f("product_id", "產品編號"), f("scope", "範疇", "integer", minimum=1),
        f("kg_co2_per_unit", "每單位 kg CO₂", "number", minimum=0),
        f("note", "備註", required=False)), "carbon_factors"),
    "carbon/target": Action("新增減碳目標", "carbon", frozenset({"admin"}), (
        f("target_year", "目標年份", "integer", minimum=2000), f("scope", "範疇", "integer", minimum=1),
        f("baseline_kg_co2", "基準 kg CO₂", "number", minimum=0),
        f("target_kg_co2", "目標 kg CO₂", "number", minimum=0),
        f("note", "備註", required=False)), "esg_targets"),
    "risk/event": Action("新增風險事件", "risk", frozenset(), (
        f("event_type", "事件類型"), f("country", "國家", required=False),
        f("region", "地區", required=False), f("impact_days", "預估延遲天數", "integer", minimum=0),
        f("description", "說明", required=False)), capability=RISK_WORKSPACE_WRITE),
}


def allowed(principal: AccessContext, action: Action) -> bool:
    return principal.can(action.capability) if action.capability else principal.role in action.roles


def catalog(principal: AccessContext) -> list[dict]:
    return [
        {"key": key, "label": action.label, "module": action.module,
         "fields": [field.__dict__ for field in action.fields]}
        for key, action in ACTIONS.items() if allowed(principal, action)
    ]


def _clean(action: Action, raw: dict) -> dict:
    keys = {field.key for field in action.fields}
    if set(raw) - keys:
        raise HTTPException(422, "包含未允許的欄位")
    values = {}
    for field in action.fields:
        value = raw.get(field.key)
        if value is None or value == "":
            if field.required:
                raise HTTPException(422, f"請填寫{field.label}")
            values[field.key] = None
            continue
        try:
            if field.kind == "integer":
                if isinstance(value, bool) or str(value).strip() != str(int(value)):
                    raise ValueError()
                value = int(value)
            elif field.kind == "number":
                value = float(value)
                if not (-1e12 < value < 1e12):
                    raise ValueError()
            elif field.kind == "date":
                value = date.fromisoformat(str(value)).isoformat()
            else:
                value = str(value).strip()
                if len(value) > 500:
                    raise ValueError()
            if field.minimum is not None and value < field.minimum:
                raise ValueError()
        except (ValueError, TypeError, OverflowError):
            raise HTTPException(422, f"{field.label}格式不正確") from None
        values[field.key] = value
    return values


def _exists(conn: sqlite3.Connection, table: str, key: str, value: str) -> bool:
    return conn.execute(f"SELECT 1 FROM {table} WHERE {key}=?", (value,)).fetchone() is not None


def execute(key: str, raw: dict, principal: AccessContext) -> dict:
    action = ACTIONS.get(key)
    if action is None:
        raise HTTPException(404, "找不到操作")
    if not allowed(principal, action):
        raise HTTPException(403, "沒有執行此操作的權限")
    values = _clean(action, raw)
    try:
        with sqlite3.connect(database.DB_FILE, timeout=10) as conn:
            conn.execute("BEGIN IMMEDIATE")
            if key == "inventory/stock-move":
                if values["move_type"] not in {"入庫", "出庫"}:
                    raise HTTPException(422, "類型只能是入庫或出庫")
                row = conn.execute("SELECT stock, warehouse_id FROM inventory WHERE product_id=?",
                                   (values["product_id"],)).fetchone()
                if row is None:
                    raise HTTPException(422, "找不到產品")
                delta = values["qty"] if values["move_type"] == "入庫" else -values["qty"]
                if (row[0] or 0) + delta < 0:
                    raise HTTPException(422, "庫存不足")
                conn.execute("UPDATE inventory SET stock=stock+? WHERE product_id=?", (delta, values["product_id"]))
                conn.execute("INSERT INTO stock_moves (product_id,warehouse_id,qty,move_type,ref_no,move_date,note) VALUES (?,?,?,?,?,?,?)",
                             (values["product_id"], row[1], delta, values["move_type"], values["ref_no"],
                              datetime.now(timezone.utc).isoformat(), values["note"]))
            elif key == "sales/quotation":
                for table, field in (("customers", "customer_id"), ("inventory", "product_id")):
                    if not _exists(conn, table, field, values[field]):
                        raise HTTPException(422, f"找不到{field}")
                total = values["qty"] * values["unit_price"]
                conn.execute("INSERT INTO quotations VALUES (?,?,?,?,?,?)",
                             (values["quote_id"], values["customer_id"], date.today().isoformat(),
                              "有效", total, values["valid_until"]))
                conn.execute("INSERT INTO quotation_items (quote_id,product_id,qty,unit_price) VALUES (?,?,?,?)",
                             (values["quote_id"], values["product_id"], values["qty"], values["unit_price"]))
            elif key == "sales/order":
                if not _exists(conn, "customers", "customer_id", values["customer_id"]):
                    raise HTTPException(422, "找不到客戶")
                row = conn.execute("SELECT stock,price FROM inventory WHERE product_id=?", (values["product_id"],)).fetchone()
                if row is None or row[0] < values["quantity"]:
                    raise HTTPException(422, "找不到產品或庫存不足")
                conn.execute("INSERT INTO orders (order_id,customer_id,product_id,quantity,status,order_date,total_amount) VALUES (?,?,?,?,?,?,?)",
                             (values["order_id"], values["customer_id"], values["product_id"], values["quantity"],
                              "處理中", datetime.now(timezone.utc).isoformat(), values["quantity"] * (row[1] or 0)))
                conn.execute("UPDATE inventory SET stock=stock-? WHERE product_id=?", (values["quantity"], values["product_id"]))
            elif key == "sales/order-status":
                if values["status"] not in {"處理中", "已出貨", "已取消"}:
                    raise HTTPException(422, "訂單狀態不正確")
                row = conn.execute("SELECT status,product_id,quantity FROM orders WHERE order_id=?", (values["order_id"],)).fetchone()
                if row is None:
                    raise HTTPException(404, "找不到訂單")
                if row[0] == "已取消" and values["status"] != "已取消":
                    raise HTTPException(422, "已取消訂單不可重新啟用")
                if values["status"] == "已取消" and row[0] != "已取消":
                    conn.execute("UPDATE inventory SET stock=stock+? WHERE product_id=?", (row[2], row[1]))
                conn.execute("UPDATE orders SET status=? WHERE order_id=?", (values["status"], values["order_id"]))
            elif key == "risk/event":
                from backend.supply_chain_risk import add_risk_event
                # This helper owns its own transaction and capability check.
                conn.rollback()
                add_risk_event(values["event_type"], values["region"], values["country"],
                               values["impact_days"], values["description"], actor=principal.username)
            else:
                if key == "inventory/product":
                    values["baseline_reorder_point"] = values["reorder_point"]
                    if values["warehouse_id"] and not _exists(conn, "warehouses", "warehouse_id", values["warehouse_id"]):
                        raise HTTPException(422, "找不到倉庫")
                if key == "procurement/supplier" and values["risk_level"] not in {None, "低", "中", "高"}:
                    raise HTTPException(422, "風險等級只能是低、中或高")
                if key == "finance/ledger" and values["debit"] == 0 and values["credit"] == 0:
                    raise HTTPException(422, "借方或貸方至少一項要大於零")
                if key in {"hr/payroll", "hr/attendance"} and not _exists(conn, "hr", "employee_id", values["employee_id"]):
                    raise HTTPException(422, "找不到員工")
                if key in {"carbon/factor"} and not _exists(conn, "inventory", "product_id", values["product_id"]):
                    raise HTTPException(422, "找不到產品")
                columns = ",".join(values)
                placeholders = ",".join("?" for _ in values)
                conn.execute(f"INSERT INTO {action.table} ({columns}) VALUES ({placeholders})", tuple(values.values()))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "資料編號已存在或不符合資料庫限制") from exc
    return {"ok": True, "message": f"{action.label}完成"}
