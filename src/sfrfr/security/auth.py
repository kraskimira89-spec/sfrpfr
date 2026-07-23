"""Проверка Supabase JWT / MAX initData и серверная RBAC-проверка."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sfrfr.core.config import get_settings
from sfrfr.db.session import get_supabase_client, get_supabase_user_client
from sfrfr.security.max_webapp import extract_max_user_id, verify_max_init_data

_bearer = HTTPBearer(auto_error=False)


class StaffRole(StrEnum):
    OPERATOR = "operator"
    EXPERT = "expert"
    ADMIN = "admin"


@dataclass(frozen=True)
class Principal:
    """Подтверждённый пользователь (JWT или MAX WebApp)."""

    user_id: str
    email: str | None
    role: StaffRole | None
    max_user_id: str | None = None
    auth_via: str = "jwt"  # jwt | max

    @property
    def is_staff(self) -> bool:
        return self.role is not None

    @property
    def is_max_only(self) -> bool:
        return self.auth_via == "max" and self.user_id.startswith("max:")

    def audit_actor_id(self) -> str | None:
        """UUID для access_audit; у MAX-only — None."""
        if self.is_max_only:
            return None
        return self.user_id


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


def _principal_from_max(max_user_id: str) -> Principal:
    """MAX WebApp → Principal; если уже linked к auth — используем UUID."""
    from sfrfr.db.client_channels import ClientChannelRepository

    row = ClientChannelRepository().ensure_for_max_user(max_user_id)
    auth_uid = row.get("user_id")
    if auth_uid:
        return Principal(
            user_id=str(auth_uid),
            email=row.get("email"),
            role=_lookup_role(str(auth_uid)),
            max_user_id=max_user_id,
            auth_via="max",
        )
    return Principal(
        user_id=f"max:{max_user_id}",
        email=None,
        role=None,
        max_user_id=max_user_id,
        auth_via="max",
    )


def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    x_max_init_data: Annotated[str | None, Header(alias="X-MAX-InitData")] = None,
    x_max_user_id: Annotated[str | None, Header(alias="X-MAX-User-Id")] = None,
) -> Principal:
    """
    Авторизация клиента:
    - Bearer JWT (веб-кабинет);
    - X-MAX-InitData (mini-app, подпись проверяется в prod);
    - X-MAX-User-Id только вне production (локальная отладка).
    """
    settings = get_settings()

    if credentials is not None and credentials.scheme.lower() == "bearer":
        if not settings.supabase_url or not settings.supabase_anon_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Supabase Auth is not configured",
            )
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
            auth_via="jwt",
        )

    if x_max_init_data and x_max_init_data.strip():
        max_uid = extract_max_user_id(x_max_init_data)
        if not max_uid:
            raise _unauthorized("MAX initData without user id")
        if settings.max_bot_token:
            ok = verify_max_init_data(x_max_init_data, settings.max_bot_token)
            if not ok and settings.app_env == "production":
                raise _unauthorized("invalid MAX init_data signature")
        elif settings.app_env == "production":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MAX_BOT_TOKEN not configured",
            )
        return _principal_from_max(max_uid)

    if x_max_user_id and x_max_user_id.strip():
        if settings.app_env == "production":
            raise _unauthorized("X-MAX-User-Id not allowed in production; use initData")
        return _principal_from_max(x_max_user_id.strip())

    raise _unauthorized()


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
