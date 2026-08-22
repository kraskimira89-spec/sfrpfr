"""Выдача staff-ролей через Supabase service role."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sfrfr.db.session import get_supabase_client
from sfrfr.security.auth import StaffRole


@dataclass(frozen=True)
class _StaffUserStub:
    """Минимальный user, когда GoTrue list_users/get_user_by_id недоступны."""

    id: str
    email: str | None = None


def _user_email(user: Any) -> str | None:
    return getattr(user, "email", None) or (user.get("email") if isinstance(user, dict) else None)


def user_id_of(user: Any) -> str:
    value = getattr(user, "id", None) or (user.get("id") if isinstance(user, dict) else None)
    if not value:
        raise RuntimeError("user without id")
    return str(value)


def _staff_row_by_email(email: str) -> dict[str, Any] | None:
    normalized = email.strip().lower()
    if not normalized or "@" not in normalized:
        return None
    client = get_supabase_client()
    try:
        rows = (
            client.table("staff_roles")
            .select("user_id, role, staff_email, max_user_id, trusted_login_max_user_id")
            .eq("staff_email", normalized)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        if "staff_email" not in str(exc).lower():
            raise
        rows = []
    if rows:
        return rows[0]
    try:
        all_rows = (
            client.table("staff_roles").select("user_id, role, staff_email").execute().data or []
        )
    except Exception as exc:  # noqa: BLE001
        if "staff_email" in str(exc).lower():
            all_rows = client.table("staff_roles").select("user_id, role").execute().data or []
        else:
            raise
    for row in all_rows:
        stored = str(row.get("staff_email") or "").strip().lower()
        if stored == normalized:
            return row
    return None


def _bootstrap_role_for_ops_email(normalized: str) -> StaffRole | None:
    """Пока нет staff_email в БД: ops_notify_email → единственный admin."""
    uid = _bootstrap_user_id_for_ops_email(normalized)
    if not uid:
        return None
    return StaffRole.ADMIN


def _bootstrap_user_id_for_ops_email(normalized: str) -> str | None:
    from sfrfr.core.config import get_settings

    ops = (get_settings().ops_notify_email or "").strip().lower()
    if not ops or normalized != ops:
        return None
    client = get_supabase_client()
    rows = (
        client.table("staff_roles")
        .select("user_id")
        .eq("role", StaffRole.ADMIN.value)
        .limit(2)
        .execute()
        .data
        or []
    )
    if len(rows) == 1:
        return str(rows[0]["user_id"])
    return None


def find_user_by_email(email: str) -> Any | None:
    """Найти пользователя Auth по email; staff_email в staff_roles — без list_users."""
    normalized = email.strip().lower()
    row = _staff_row_by_email(normalized)
    client = get_supabase_client()
    if row:
        uid = str(row["user_id"])
        try:
            client.auth.admin.get_user_by_id(uid)
            return _StaffUserStub(uid, normalized)
        except Exception:  # noqa: BLE001 — устаревший user_id в staff_roles
            pass

    boot_uid = _bootstrap_user_id_for_ops_email(normalized)
    if boot_uid:
        try:
            client.auth.admin.get_user_by_id(boot_uid)
            return _StaffUserStub(boot_uid, normalized)
        except Exception:  # noqa: BLE001
            pass
    page = 1
    per_page = 200
    try:
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
    except Exception:  # noqa: BLE001
        return None


def sync_staff_role_auth_user_id(*, email: str, auth_user_id: str) -> bool:
    """Привязать staff_roles.user_id к реальному UUID Supabase Auth (после MAX/OTP входа)."""
    normalized = email.strip().lower()
    auth_uid = str(auth_user_id).strip()
    if not normalized or "@" not in normalized or not auth_uid:
        return False
    row = _staff_row_by_email(normalized)
    if not row:
        return False
    stored_uid = str(row.get("user_id") or "").strip()
    if stored_uid == auth_uid:
        return False
    client = get_supabase_client()
    payload: dict[str, Any] = {"user_id": auth_uid, "staff_email": normalized}
    try:
        client.table("staff_roles").update(payload).eq("user_id", stored_uid).execute()
    except Exception as exc:  # noqa: BLE001
        if "staff_email" not in str(exc).lower():
            raise
        client.table("staff_roles").update({"user_id": auth_uid}).eq(
            "user_id", stored_uid
        ).execute()
    return True


def ensure_user(email: str, *, invite: bool) -> Any:
    """Вернуть существующего пользователя или создать/пригласить."""
    normalized = email.strip().lower()
    existing = find_user_by_email(normalized)
    if existing is not None:
        return existing
    if not invite:
        raise LookupError(
            f"Пользователь {normalized} не найден. Сначала войдите по OTP или добавьте --invite."
        )
    client = get_supabase_client()
    try:
        created = client.auth.admin.create_user(
            {
                "email": normalized,
                "email_confirm": True,
                "app_metadata": {"role_source": "staff_bootstrap"},
            }
        )
    except Exception as exc:
        err = str(exc).lower()
        if "already" in err or "registered" in err:
            row = _staff_row_by_email(normalized)
            if row:
                return _StaffUserStub(str(row["user_id"]), normalized)
        raise
    user = getattr(created, "user", created)
    if user is None:
        raise RuntimeError("не удалось создать пользователя Auth")
    return user


def grant_staff_role(
    user_id: str,
    role: StaffRole | str,
    *,
    staff_email: str | None = None,
) -> dict[str, Any]:
    role_value = role.value if isinstance(role, StaffRole) else StaffRole(role).value
    payload: dict[str, Any] = {"user_id": user_id, "role": role_value}
    if staff_email and "@" in staff_email:
        payload["staff_email"] = staff_email.strip().lower()
    client = get_supabase_client()
    try:
        response = client.table("staff_roles").upsert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        if "staff_email" in str(exc).lower():
            payload.pop("staff_email", None)
            response = client.table("staff_roles").upsert(payload).execute()
        else:
            raise
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
        email = (row.get("staff_email") or "").strip() or None
        if not email:
            try:
                user = client.auth.admin.get_user_by_id(str(row["user_id"]))
                email = _user_email(getattr(user, "user", user))
            except Exception:  # noqa: BLE001 - CLI boundary
                email = None
        enriched.append({**row, "email": email})
    return enriched


def get_staff_role_by_email(email: str) -> StaffRole | None:
    """Роль сотрудника по рабочему email или None."""
    normalized = email.strip().lower()
    row = _staff_row_by_email(normalized)
    if row:
        try:
            return StaffRole(str(row["role"]))
        except ValueError:
            return None

    boot = _bootstrap_role_for_ops_email(normalized)
    if boot is not None:
        return boot

    user = find_user_by_email(normalized)
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


def _staff_user_id_for_email(email: str) -> str | None:
    normalized = email.strip().lower()
    row = _staff_row_by_email(normalized)
    if row:
        return str(row["user_id"])
    boot_uid = _bootstrap_user_id_for_ops_email(normalized)
    if boot_uid:
        return boot_uid
    user = find_user_by_email(email)
    return user_id_of(user) if user else None


def is_staff_login_trusted(*, email: str, max_user_id: str) -> bool:
    """True, если этот MAX уже одобрен руководителем для email (повторный вход)."""
    trusted = trusted_login_max_user_id(email)
    return bool(trusted) and trusted == str(max_user_id).strip()


def trusted_login_max_user_id(email: str) -> str | None:
    """MAX user_id для повторного входа сотрудника или None."""
    user_id = _staff_user_id_for_email(email)
    if not user_id:
        return None
    client = get_supabase_client()
    rows = (
        client.table("staff_roles")
        .select("trusted_login_max_user_id")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return None
    trusted = str(rows[0].get("trusted_login_max_user_id") or "").strip()
    return trusted or None


def trust_staff_login(*, email: str, max_user_id: str) -> dict[str, Any] | None:
    """Запомнить MAX после первого одобрения руководителем."""
    from datetime import UTC, datetime

    user_id = _staff_user_id_for_email(email)
    if not user_id:
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
        .eq("user_id", user_id)
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
