"""Безопасные операции со staff_roles: guards, invite, audit (P0)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import HTTPException, status

from sfrfr.db.session import get_supabase_client
from sfrfr.security.auth import StaffRole

AuditResult = Literal["success", "denied", "error"]

INVITE_TTL_HOURS = 72
ALLOWED_STATUSES = frozenset({"active", "invited", "suspended", "archived"})


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def write_staff_audit(
    *,
    actor_id: str | None,
    target_user_id: str | None,
    event: str,
    result: AuditResult = "success",
    old_role: str | None = None,
    new_role: str | None = None,
    old_status: str | None = None,
    new_status: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    get_supabase_client().table("staff_access_audit").insert(
        {
            "actor_id": actor_id,
            "target_user_id": target_user_id,
            "event": event,
            "result": result,
            "old_role": old_role,
            "new_role": new_role,
            "old_status": old_status,
            "new_status": new_status,
            "ip": (ip or "")[:120] or None,
            "user_agent": (user_agent or "")[:500] or None,
            "meta": meta or {},
        }
    ).execute()


def get_staff_row(user_id: str) -> dict[str, Any] | None:
    rows = (
        get_supabase_client()
        .table("staff_roles")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def get_staff_row_by_email(email: str) -> dict[str, Any] | None:
    normalized = email.strip().lower()
    try:
        rows = (
            get_supabase_client()
            .table("staff_roles")
            .select("*")
            .eq("staff_email", normalized)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001
        return None
    return rows[0] if rows else None


def count_active_admins(*, exclude_user_id: str | None = None) -> int:
    rows = (
        get_supabase_client()
        .table("staff_roles")
        .select("user_id")
        .eq("role", StaffRole.ADMIN.value)
        .eq("status", "active")
        .execute()
        .data
        or []
    )
    if exclude_user_id:
        rows = [r for r in rows if str(r["user_id"]) != exclude_user_id]
    return len(rows)


def serialize_member(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": str(row["user_id"]),
        "email": row.get("staff_email") or row.get("email"),
        "display_name": row.get("display_name"),
        "role": row.get("role"),
        "status": row.get("status") or "active",
        "last_sign_in_at": row.get("last_sign_in_at"),
        "invited_at": row.get("invited_at"),
        "invite_expires_at": row.get("invite_expires_at"),
        "created_at": row.get("created_at"),
    }


def list_staff_members() -> list[dict[str, Any]]:
    from sfrfr.db.staff_roles import list_staff_roles

    return [serialize_member(row) for row in list_staff_roles()]


def list_staff_audit(target_user_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    return (
        get_supabase_client()
        .table("staff_access_audit")
        .select(
            "id, at, actor_id, target_user_id, event, old_role, new_role, "
            "old_status, new_status, result"
        )
        .eq("target_user_id", target_user_id)
        .order("at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )


def _deny(
    *,
    actor_id: str,
    target_user_id: str,
    event: str,
    detail: str,
    old_role: str | None = None,
    new_role: str | None = None,
    old_status: str | None = None,
    new_status: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    write_staff_audit(
        actor_id=actor_id,
        target_user_id=target_user_id,
        event=event,
        result="denied",
        old_role=old_role,
        new_role=new_role,
        old_status=old_status,
        new_status=new_status,
        ip=ip,
        user_agent=user_agent,
        meta={"detail": detail},
    )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def validate_staff_change(
    *,
    actor_id: str,
    target_user_id: str,
    old_role: str | None,
    new_role: str,
    old_status: str | None,
    new_status: str,
    confirm_admin_grant: bool,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    if new_status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="Некорректный статус сотрудника")
    try:
        StaffRole(new_role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Некорректная роль") from exc

    role_changed = (old_role or "") != new_role
    status_changed = (old_status or "active") != new_status

    if actor_id == target_user_id and (role_changed or status_changed):
        _deny(
            actor_id=actor_id,
            target_user_id=target_user_id,
            event="staff_self_change",
            detail="Нельзя менять свою роль или статус через интерфейс",
            old_role=old_role,
            new_role=new_role,
            old_status=old_status,
            new_status=new_status,
            ip=ip,
            user_agent=user_agent,
        )

    was_active_admin = old_role == StaffRole.ADMIN.value and (old_status or "active") == "active"
    stays_active_admin = new_role == StaffRole.ADMIN.value and new_status == "active"
    if was_active_admin and not stays_active_admin:
        if count_active_admins(exclude_user_id=target_user_id) < 1:
            _deny(
                actor_id=actor_id,
                target_user_id=target_user_id,
                event="staff_last_admin",
                detail="Нельзя понизить или приостановить последнего активного администратора",
                old_role=old_role,
                new_role=new_role,
                old_status=old_status,
                new_status=new_status,
                ip=ip,
                user_agent=user_agent,
            )

    granting_admin = new_role == StaffRole.ADMIN.value and (
        old_role != StaffRole.ADMIN.value or (old_status or "active") != "active"
    )
    if granting_admin and not confirm_admin_grant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для назначения роли admin подтвердите confirm_admin_grant=true",
        )


def patch_staff_member(
    *,
    actor_id: str,
    target_user_id: str,
    role: str | None = None,
    status_value: str | None = None,
    display_name: str | None = None,
    confirm_admin_grant: bool = False,
    ip: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    row = get_staff_row(target_user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    old_role = str(row.get("role") or "")
    old_status = str(row.get("status") or "active")
    new_role = role if role is not None else old_role
    new_status = status_value if status_value is not None else old_status

    validate_staff_change(
        actor_id=actor_id,
        target_user_id=target_user_id,
        old_role=old_role,
        new_role=new_role,
        old_status=old_status,
        new_status=new_status,
        confirm_admin_grant=confirm_admin_grant,
        ip=ip,
        user_agent=user_agent,
    )

    payload: dict[str, Any] = {"role": new_role, "status": new_status}
    if display_name is not None:
        payload["display_name"] = display_name.strip() or None
    if new_status == "suspended" and old_status != "suspended":
        payload["suspended_at"] = _iso(_now())
    if new_status == "active":
        payload["suspended_at"] = None
        payload["invite_token_hash"] = None
        payload["invite_expires_at"] = None
    if new_status == "archived":
        payload["invite_token_hash"] = None

    client = get_supabase_client()
    response = (
        client.table("staff_roles").update(payload).eq("user_id", target_user_id).execute()
    )
    if not response.data:
        write_staff_audit(
            actor_id=actor_id,
            target_user_id=target_user_id,
            event="staff_patch",
            result="error",
            old_role=old_role,
            new_role=new_role,
            old_status=old_status,
            new_status=new_status,
            ip=ip,
            user_agent=user_agent,
        )
        raise HTTPException(status_code=500, detail="Не удалось обновить сотрудника")

    write_staff_audit(
        actor_id=actor_id,
        target_user_id=target_user_id,
        event="staff_patch",
        result="success",
        old_role=old_role,
        new_role=new_role,
        old_status=old_status,
        new_status=new_status,
        ip=ip,
        user_agent=user_agent,
    )
    client.table("access_audit").insert(
        {
            "actor_id": actor_id,
            "case_id": None,
            "action": f"staff_role_upsert:{new_role}:{new_status}",
        }
    ).execute()
    return serialize_member(response.data[0])


def invite_staff_member(
    *,
    actor_id: str,
    email: str,
    display_name: str,
    role: str,
    confirm_admin_grant: bool = False,
    ip: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    from sfrfr.db.staff_roles import ensure_user, grant_staff_role, user_id_of

    normalized = email.strip().lower()
    name = display_name.strip()
    if not normalized or "@" not in normalized:
        raise HTTPException(status_code=400, detail="Укажите рабочий e-mail")
    if not name:
        raise HTTPException(status_code=400, detail="Укажите имя и фамилию")
    try:
        staff_role = StaffRole(role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Некорректная роль") from exc

    if staff_role is StaffRole.ADMIN and not confirm_admin_grant:
        raise HTTPException(
            status_code=400,
            detail="Для приглашения admin подтвердите confirm_admin_grant=true",
        )

    existing = get_staff_row_by_email(normalized)
    if existing and str(existing.get("status") or "") != "archived":
        raise HTTPException(status_code=409, detail="Сотрудник с таким e-mail уже есть")

    try:
        user = ensure_user(normalized, invite=True)
    except Exception as exc:  # noqa: BLE001
        write_staff_audit(
            actor_id=actor_id,
            target_user_id=None,
            event="staff_invite_create",
            result="error",
            new_role=staff_role.value,
            new_status="invited",
            ip=ip,
            user_agent=user_agent,
            meta={"email_domain": normalized.split("@")[-1], "detail": str(exc)[:200]},
        )
        raise HTTPException(
            status_code=502, detail="Не удалось создать пользователя Auth"
        ) from exc

    uid = user_id_of(user)
    if uid == actor_id:
        _deny(
            actor_id=actor_id,
            target_user_id=uid,
            event="staff_self_change",
            detail="Нельзя пригласить самого себя",
            new_role=staff_role.value,
            new_status="invited",
            ip=ip,
            user_agent=user_agent,
        )

    token = secrets.token_urlsafe(32)
    expires = _now() + timedelta(hours=INVITE_TTL_HOURS)
    grant_staff_role(uid, staff_role, staff_email=normalized)

    response = (
        get_supabase_client()
        .table("staff_roles")
        .update(
            {
                "status": "invited",
                "display_name": name,
                "staff_email": normalized,
                "invited_at": _iso(_now()),
                "invite_expires_at": _iso(expires),
                "invite_token_hash": _hash_token(token),
                "suspended_at": None,
            }
        )
        .eq("user_id", uid)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=500, detail="Не удалось сохранить приглашение")

    invite_sent = _try_send_invite_email(normalized)
    write_staff_audit(
        actor_id=actor_id,
        target_user_id=uid,
        event="staff_invite_create",
        result="success",
        new_role=staff_role.value,
        new_status="invited",
        ip=ip,
        user_agent=user_agent,
        meta={"invite_sent": invite_sent, "email_domain": normalized.split("@")[-1]},
    )
    if invite_sent:
        write_staff_audit(
            actor_id=actor_id,
            target_user_id=uid,
            event="staff_invite_send",
            result="success",
            new_role=staff_role.value,
            new_status="invited",
            ip=ip,
            user_agent=user_agent,
        )

    member = serialize_member(response.data[0])
    member["invite_expires_at"] = _iso(expires)
    return member


def revoke_invite(
    *,
    actor_id: str,
    target_user_id: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    row = get_staff_row(target_user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    if str(row.get("status") or "") != "invited":
        raise HTTPException(status_code=400, detail="Отозвать можно только приглашение")
    return patch_staff_member(
        actor_id=actor_id,
        target_user_id=target_user_id,
        status_value="archived",
        confirm_admin_grant=False,
        ip=ip,
        user_agent=user_agent,
    )


def _try_send_invite_email(email: str) -> bool:
    client = get_supabase_client()
    try:
        invite = getattr(client.auth.admin, "invite_user_by_email", None)
        if callable(invite):
            invite(email)
            return True
    except Exception:  # noqa: BLE001
        return False
    return False


def mark_staff_signed_in(user_id: str) -> None:
    row = get_staff_row(user_id)
    if not row:
        return
    status_value = str(row.get("status") or "active")
    if status_value in {"suspended", "archived"}:
        return
    payload: dict[str, Any] = {"last_sign_in_at": _iso(_now())}
    if status_value == "invited":
        expires = row.get("invite_expires_at")
        if expires:
            try:
                exp_dt = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
                if exp_dt < _now():
                    return
            except ValueError:
                pass
        payload.update(
            {
                "status": "active",
                "invite_token_hash": None,
                "invite_expires_at": None,
            }
        )
        write_staff_audit(
            actor_id=user_id,
            target_user_id=user_id,
            event="staff_invite_accept",
            result="success",
            old_role=str(row.get("role")),
            new_role=str(row.get("role")),
            old_status="invited",
            new_status="active",
        )
    get_supabase_client().table("staff_roles").update(payload).eq("user_id", user_id).execute()


def assert_staff_status_allows_login(user_id: str) -> None:
    row = get_staff_row(user_id)
    if not row:
        return
    st = str(row.get("status") or "active")
    if st in {"suspended", "archived"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ сотрудника приостановлен или архивирован",
        )
