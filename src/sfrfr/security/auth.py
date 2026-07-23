"""Проверка Supabase JWT и серверная RBAC-проверка."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sfrfr.core.config import get_settings
from sfrfr.db.session import get_supabase_client, get_supabase_user_client

_bearer = HTTPBearer(auto_error=False)


class StaffRole(StrEnum):
    OPERATOR = "operator"
    EXPERT = "expert"
    ADMIN = "admin"


@dataclass(frozen=True)
class Principal:
    """Подтверждённый пользователь Supabase Auth."""

    user_id: str
    email: str | None
    role: StaffRole | None

    @property
    def is_staff(self) -> bool:
        return self.role is not None


def _unauthorized(detail: str = "authentication required") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _lookup_role(user_id: str) -> StaffRole | None:
    """Роли читаются только server-side service client, не из user_metadata."""
    response = (
        get_supabase_client()
        .table("staff_roles")
        .select("role")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    row: dict[str, Any] | None = response.data
    if not row:
        return None
    try:
        return StaffRole(str(row["role"]))
    except (KeyError, ValueError):
        return None


def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    """Проверить access token через Supabase Auth."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase Auth is not configured",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        user = get_supabase_user_client().auth.get_user(credentials.credentials).user
    except Exception as exc:  # noqa: BLE001 - HTTP boundary
        raise _unauthorized("invalid or expired access token") from exc
    if user is None:
        raise _unauthorized("invalid access token")

    return Principal(
        user_id=str(user.id),
        email=getattr(user, "email", None),
        role=_lookup_role(str(user.id)),
    )


def require_staff(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Principal:
    if not principal.is_staff:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="staff role required")
    return principal


def require_admin(
    principal: Annotated[Principal, Depends(require_staff)],
) -> Principal:
    if principal.role is not StaffRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin role required")
    return principal
