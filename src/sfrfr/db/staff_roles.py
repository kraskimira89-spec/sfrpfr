"""Выдача staff-ролей через Supabase service role."""

from __future__ import annotations

from typing import Any

from sfrfr.db.session import get_supabase_client
from sfrfr.security.auth import StaffRole


def _user_email(user: Any) -> str | None:
    return getattr(user, "email", None) or (user.get("email") if isinstance(user, dict) else None)


def user_id_of(user: Any) -> str:
    value = getattr(user, "id", None) or (user.get("id") if isinstance(user, dict) else None)
    if not value:
        raise RuntimeError("user without id")
    return str(value)


def find_user_by_email(email: str) -> Any | None:
    """Найти пользователя Auth по email (admin API)."""
    client = get_supabase_client()
    normalized = email.strip().lower()
    page = 1
    per_page = 200
    while True:
        response = client.auth.admin.list_users(page=page, per_page=per_page)
        users = getattr(response, "users", None) or response or []
        if not users:
            return None
        for user in users:
            if (_user_email(user) or "").lower() == normalized:
                return user
        if len(users) < per_page:
            return None
        page += 1


def ensure_user(email: str, *, invite: bool) -> Any:
    """Вернуть существующего пользователя или создать/пригласить."""
    existing = find_user_by_email(email)
    if existing is not None:
        return existing
    if not invite:
        raise LookupError(
            f"Пользователь {email} не найден. Сначала войдите по OTP или добавьте --invite."
        )
    client = get_supabase_client()
    # invite_user_by_email шлёт письмо; create_user — для bootstrap без SMTP.
    created = client.auth.admin.create_user(
        {
            "email": email.strip().lower(),
            "email_confirm": True,
            "app_metadata": {"role_source": "staff_bootstrap"},
        }
    )
    user = getattr(created, "user", created)
    if user is None:
        raise RuntimeError("не удалось создать пользователя Auth")
    return user


def grant_staff_role(user_id: str, role: StaffRole | str) -> dict[str, Any]:
    role_value = role.value if isinstance(role, StaffRole) else StaffRole(role).value
    client = get_supabase_client()
    response = (
        client.table("staff_roles")
        .upsert({"user_id": user_id, "role": role_value})
        .execute()
    )
    if not response.data:
        raise RuntimeError("upsert staff_roles вернул пустой ответ")
    client.table("access_audit").insert(
        {
            "actor_id": user_id,
            "case_id": None,
            "action": f"staff_role_bootstrap:{role_value}",
        }
    ).execute()
    return response.data[0]


def list_staff_roles() -> list[dict[str, Any]]:
    client = get_supabase_client()
    rows = client.table("staff_roles").select("*").order("created_at").execute().data or []
    enriched: list[dict[str, Any]] = []
    for row in rows:
        email = None
        try:
            user = client.auth.admin.get_user_by_id(str(row["user_id"]))
            email = _user_email(getattr(user, "user", user))
        except Exception:  # noqa: BLE001 - CLI boundary
            email = None
        enriched.append({**row, "email": email})
    return enriched


def get_staff_role_by_email(email: str) -> StaffRole | None:
    """Роль сотрудника по рабочему email или None."""
    user = find_user_by_email(email)
    if user is None:
        return None
    client = get_supabase_client()
    rows = (
        client.table("staff_roles")
        .select("role")
        .eq("user_id", user_id_of(user))
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return None
    try:
        return StaffRole(str(rows[0]["role"]))
    except ValueError:
        return None


def is_staff_login_trusted(*, email: str, max_user_id: str) -> bool:
    """True, если этот MAX уже одобрен руководителем для email (повторный вход)."""
    user = find_user_by_email(email)
    if user is None:
        return False
    client = get_supabase_client()
    rows = (
        client.table("staff_roles")
        .select("trusted_login_max_user_id")
        .eq("user_id", user_id_of(user))
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return False
    trusted = str(rows[0].get("trusted_login_max_user_id") or "").strip()
    return bool(trusted) and trusted == str(max_user_id).strip()


def trust_staff_login(*, email: str, max_user_id: str) -> dict[str, Any] | None:
    """Запомнить MAX после первого одобрения руководителем."""
    from datetime import UTC, datetime

    user = find_user_by_email(email)
    if user is None:
        return None
    client = get_supabase_client()
    response = (
        client.table("staff_roles")
        .update(
            {
                "trusted_login_max_user_id": str(max_user_id).strip(),
                "trusted_login_at": datetime.now(UTC).isoformat(),
            }
        )
        .eq("user_id", user_id_of(user))
        .execute()
    )
    return response.data[0] if response.data else None


def set_staff_max_user_id(*, user_id: str, max_user_id: str) -> dict[str, Any]:
    """Привязать MAX к строке staff_roles (для уведомлений руководителю)."""
    client = get_supabase_client()
    response = (
        client.table("staff_roles")
        .update({"max_user_id": str(max_user_id)})
        .eq("user_id", user_id)
        .execute()
    )
    if not response.data:
        raise RuntimeError("staff_roles max_user_id update empty")
    return response.data[0]


def list_manager_max_user_ids(*, extra_ids: str = "") -> list[str]:
    """MAX id руководителей: admin в staff_roles + STAFF_LOGIN_APPROVER_MAX_USER_IDS."""
    ids: list[str] = []
    seen: set[str] = set()
    for part in (extra_ids or "").split(","):
        uid = part.strip()
        if uid and uid not in seen:
            seen.add(uid)
            ids.append(uid)
    try:
        client = get_supabase_client()
        rows = (
            client.table("staff_roles")
            .select("max_user_id, role")
            .eq("role", StaffRole.ADMIN.value)
            .execute()
            .data
            or []
        )
        for row in rows:
            uid = str(row.get("max_user_id") or "").strip()
            if uid and uid not in seen:
                seen.add(uid)
                ids.append(uid)
    except Exception:  # noqa: BLE001 - env-only fallback
        pass
    return ids
