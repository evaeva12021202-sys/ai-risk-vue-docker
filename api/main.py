"""Read-only supply-chain API for the independent Vue demonstration."""

from __future__ import annotations

import base64
import binascii
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import math
import os
import secrets
import sqlite3
import time

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field

from backend import database
from backend.access_control import RISK_OVERVIEW_READ, AccessContext, load_principal
from backend.passwords import verify_password
from backend import supply_chain_risk
from api.demo_data import seed_assignment_examples


COOKIE_NAME = "vue_erp_session"
SESSION_SECONDS = 8 * 60 * 60
_session_key = os.environ.get("API_SESSION_SECRET", "").encode() or secrets.token_bytes(32)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class SessionResponse(BaseModel):
    username: str
    name: str
    role: str
    capabilities: list[str]


class RiskRegion(BaseModel):
    region_key: str
    display_name: str
    latitude: float
    longitude: float
    risk_pct: float
    ai_summary: str | None = None
    updated_at: str | None = None


class RiskEvent(BaseModel):
    id: int
    event_type: str
    region: str | None = None
    country: str | None = None
    impact_days: int
    description: str | None = None
    created_at: str | None = None


class SupplierAlert(BaseModel):
    supplier_id: str
    name: str
    country: str | None = None
    region: str | None = None
    risk_level: str


class OverviewResponse(BaseModel):
    generated_at: str
    kpis: dict[str, int]
    regions: list[RiskRegion]
    events: list[RiskEvent]
    high_risk_suppliers: list[SupplierAlert]


class PurchaseOrderSummary(BaseModel):
    po_id: str
    supplier_id: str
    supplier_name: str
    status: str | None = None
    order_date: str | None = None
    items: str | None = None
    estimated_delay_days: int | None = None


class RegionDetails(BaseModel):
    region_key: str
    suppliers: list[SupplierAlert]
    events: list[RiskEvent]
    open_purchase_orders: list[PurchaseOrderSummary]


def _encode_session(username: str) -> str:
    expiry = int(time.time()) + SESSION_SECONDS
    payload = f"{username}:{expiry}".encode()
    signature = hmac.new(_session_key, payload, hashlib.sha256).hexdigest().encode()
    return base64.urlsafe_b64encode(payload + b"." + signature).decode()


def _decode_session(token: str | None) -> str | None:
    if not token:
        return None
    try:
        raw = base64.urlsafe_b64decode(token.encode())
        payload, signature = raw.rsplit(b".", 1)
        expected = hmac.new(_session_key, payload, hashlib.sha256).hexdigest().encode()
        if not hmac.compare_digest(signature, expected):
            return None
        username, expiry = payload.decode().rsplit(":", 1)
        if not username or int(expiry) < int(time.time()):
            return None
        return username
    except (binascii.Error, ValueError, UnicodeError):
        return None


def _principal(token: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> AccessContext:
    username = _decode_session(token)
    principal = load_principal(username) if username else None
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="請先登入")
    return principal


def _session_response(principal: AccessContext) -> SessionResponse:
    return SessionResponse(
        username=principal.username,
        name=principal.name,
        role=principal.role,
        capabilities=sorted(principal.capabilities),
    )


def _text(value: object) -> str | None:
    if value is None:
        return None
    try:
        if value != value:  # Pandas NaN
            return None
    except (TypeError, ValueError):
        return None
    return str(value)


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.init_db()
    seed_assignment_examples()
    yield


app = FastAPI(title="Supply Chain Vue Assignment API", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/session", response_model=SessionResponse)
def login(credentials: LoginRequest, response: Response) -> SessionResponse:
    username = credentials.username.strip()
    with sqlite3.connect(database.DB_FILE) as conn:
        row = conn.execute(
            "SELECT password FROM users WHERE username = ?", (username,)
        ).fetchone()
    if row is None or not verify_password(credentials.password, row[0] or ""):
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
    principal = load_principal(username)
    if principal is None or not principal.can(RISK_OVERVIEW_READ):
        raise HTTPException(status_code=403, detail="沒有供應鏈風險總覽權限")
    response.set_cookie(
        COOKIE_NAME,
        _encode_session(username),
        max_age=SESSION_SECONDS,
        httponly=True,
        secure=os.environ.get("API_SECURE_COOKIE", "").lower() == "true",
        samesite="strict",
        path="/api",
    )
    return _session_response(principal)


@app.get("/api/session", response_model=SessionResponse)
def current_session(principal: AccessContext = Depends(_principal)) -> SessionResponse:
    return _session_response(principal)


@app.delete("/api/session", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/api", samesite="strict")


@app.get("/api/overview", response_model=OverviewResponse)
def overview(principal: AccessContext = Depends(_principal)) -> OverviewResponse:
    if not principal.can(RISK_OVERVIEW_READ):
        raise HTTPException(status_code=403, detail="沒有供應鏈風險總覽權限")

    kpis = supply_chain_risk.get_supply_chain_summary_kpis()
    regions = []
    for row in supply_chain_risk.get_risk_heatmap_data():
        lat, lon = row.get("latitude"), row.get("longitude")
        try:
            latitude, longitude = float(lat), float(lon)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(latitude) or not math.isfinite(longitude):
            continue
        try:
            risk_pct = float(row.get("risk_pct"))
        except (TypeError, ValueError):
            risk_pct = 0.0
        if not math.isfinite(risk_pct):
            risk_pct = 0.0
        regions.append(
            RiskRegion(
                region_key=str(row["region_key"]),
                display_name=str(row["display_name"]),
                latitude=latitude,
                longitude=longitude,
                risk_pct=risk_pct,
                ai_summary=_text(row.get("ai_summary")),
                updated_at=_text(row.get("updated_at")),
            )
        )
    regions.sort(key=lambda item: item.risk_pct, reverse=True)

    event_frame = supply_chain_risk.get_risk_events_list(limit=8)
    events = [
        RiskEvent(
            id=int(row["id"]),
            event_type=str(row.get("event_type") or "未分類"),
            region=_text(row.get("region")),
            country=_text(row.get("country")),
            impact_days=int(row.get("impact_days") or 0),
            description=_text(row.get("description")),
            created_at=_text(row.get("created_at")),
        )
        for row in event_frame.to_dict("records")
    ]

    with sqlite3.connect(database.DB_FILE) as conn:
        suppliers = conn.execute(
            "SELECT supplier_id, name, country, region, risk_level FROM suppliers "
            "WHERE risk_level = '高' ORDER BY name LIMIT 8"
        ).fetchall()
    return OverviewResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        kpis={key: int(value) for key, value in kpis.items()},
        regions=regions,
        events=events,
        high_risk_suppliers=[
            SupplierAlert(
                supplier_id=row[0], name=row[1], country=row[2],
                region=row[3], risk_level=row[4]
            )
            for row in suppliers
        ],
    )


@app.get("/api/regions/{region_key}/details", response_model=RegionDetails)
def region_details(
    region_key: str, principal: AccessContext = Depends(_principal)
) -> RegionDetails:
    if not principal.can(RISK_OVERVIEW_READ):
        raise HTTPException(status_code=403, detail="沒有供應鏈風險總覽權限")
    if region_key not in {
        row["region_key"] for row in supply_chain_risk.get_risk_heatmap_data()
    }:
        raise HTTPException(status_code=404, detail="找不到這個據點")
    country, region = region_key.split("|", 1)
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        suppliers = conn.execute(
            "SELECT supplier_id, name, country, region, risk_level FROM suppliers "
            "WHERE country = ? AND region = ? ORDER BY name",
            (country, region),
        ).fetchall()
        events = conn.execute(
            "SELECT id, event_type, region, country, impact_days, description, "
            "created_at FROM supply_chain_events "
            "WHERE (country = ? AND (region = ? OR COALESCE(region, '') = '')) "
            "OR (COALESCE(country, '') = '' AND region = ?) "
            "ORDER BY created_at DESC, id DESC LIMIT 20",
            (country, region, region),
        ).fetchall()
        orders = conn.execute(
            "SELECT p.po_id, p.supplier_id, s.name AS supplier_name, "
            "p.status, p.order_date, "
            "p.estimated_delay_days, "
            "(SELECT group_concat(COALESCE(i.name, pi.product_id), '、') "
            "FROM purchase_order_items pi LEFT JOIN inventory i "
            "ON i.product_id = pi.product_id WHERE pi.po_id = p.po_id) AS items "
            "FROM purchase_orders p JOIN suppliers s "
            "ON s.supplier_id = p.supplier_id "
            "WHERE s.country = ? AND s.region = ? "
            "AND (p.status IS NULL OR p.status NOT IN ('已完成', '已取消')) "
            "ORDER BY p.order_date DESC, p.po_id DESC",
            (country, region),
        ).fetchall()
    return RegionDetails(
        region_key=region_key,
        suppliers=[
            SupplierAlert(
                supplier_id=row["supplier_id"], name=row["name"],
                country=row["country"], region=row["region"],
                risk_level=row["risk_level"] or "未標記",
            ) for row in suppliers
        ],
        events=[
            RiskEvent(
                id=row["id"], event_type=row["event_type"] or "未分類",
                region=row["region"], country=row["country"],
                impact_days=row["impact_days"] or 0,
                description=row["description"], created_at=row["created_at"],
            ) for row in events
        ],
        open_purchase_orders=[
            PurchaseOrderSummary(
                po_id=row["po_id"], supplier_id=row["supplier_id"],
                supplier_name=row["supplier_name"],
                status=row["status"], order_date=row["order_date"],
                items=row["items"],
                estimated_delay_days=row["estimated_delay_days"],
            ) for row in orders
        ],
    )
