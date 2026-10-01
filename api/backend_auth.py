"""API-local role context for legacy AI tools; never trusts Streamlit state."""

from contextlib import contextmanager
from contextvars import ContextVar

from backend.database import run_query
from backend.passwords import verify_password

_role: ContextVar[str | None] = ContextVar("api_authenticated_role", default=None)


@contextmanager
def acting_as(role: str):
    token = _role.set(role)
    try:
        yield
    finally:
        _role.reset(token)


def check_permission(allowed_roles: list[str]) -> bool:
    role = _role.get()
    return role == "admin" or role in allowed_roles


def check_login(username: str, password: str) -> dict | None:
    rows = run_query("SELECT password, role, name FROM users WHERE username=?", (username,))
    if not rows or not verify_password(password, rows[0][0] or ""):
        return None
    return {"role": rows[0][1], "name": rows[0][2]}
