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
