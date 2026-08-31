"""Клиентский профиль: каналы MAX / веб-кабинет."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status

from sfrfr.db.session import get_supabase_client

_CHANNELS = frozenset({"max_miniapp", "web_cabinet", "unset"})
_log = logging.getLogger(__name__)


class ClientChannelRepository:
    def __init__(self) -> None:
        self.client = get_supabase_client()

    @staticmethod
    def _one_or_none(response: Any) -> dict[str, Any] | None:
        rows = getattr(response, "data", None) or []
        if isinstance(rows, dict):
            return rows
        if isinstance(rows, list) and rows:
            return rows[0]
        return None

    def get_by_user_id(self, user_id: str) -> dict[str, Any] | None:
        # limit(1), не maybe_single: пустой результат не должен бросать исключение
        return self._one_or_none(
            self.client.table("clients")
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

    def get_by_max_user_id(self, max_user_id: str) -> dict[str, Any] | None:
        return self._one_or_none(
            self.client.table("clients")
            .select("*")
            .eq("max_user_id", str(max_user_id))
            .limit(1)
            .execute()
        )

    def ensure_for_auth_user(
        self,
        user_id: str,
        *,
        email: str | None = None,
        full_name: str = "Клиент",
        phone: str | None = None,
    ) -> dict[str, Any]:
        existing = self.get_by_user_id(user_id)
        if existing:
            if phone and not str(existing.get("phone") or "").strip():
                updated = self._one_or_none(
                    self.client.table("clients")
                    .update({"phone": phone})
                    .eq("id", existing["id"])
                    .execute()
                )
                return updated or existing
            return existing
        payload: dict[str, Any] = {
            "user_id": user_id,
            "full_name": full_name,
            "preferred_channel": "unset",
        }
        if email:
            payload["email"] = email
        if phone:
            payload["phone"] = phone
        response = self.client.table("clients").insert(payload).execute()
        row = self._one_or_none(response)
        if not row:
            raise RuntimeError("clients insert returned empty for auth user")
        return row

    def _ensure_auth_user_for_max(self, max_user_id: str, email: str) -> str | None:
        """Создать/найти auth.users для MAX-клиента; вернуть uuid или None."""
        try:
            from sfrfr.db.staff_roles import find_user_by_email

            existing = find_user_by_email(email)
            if existing and existing.get("id"):
                return str(existing["id"])
            created = self.client.auth.admin.create_user(
                {
                    "email": email,
                    "email_confirm": True,
                    "app_metadata": {
                        "role_source": "max_channel",
                        "max_user_id": str(max_user_id),
                    },
                }
            )
            user = getattr(created, "user", None)
            if user is None and isinstance(created, dict):
                user = created.get("user") or created
            uid = getattr(user, "id", None) if user is not None else None
            if uid is None and isinstance(user, dict):
                uid = user.get("id")
            return str(uid) if uid else None
        except Exception as exc:  # noqa: BLE001
            _log.warning("max_auth_user_ensure_failed max=%s: %s", max_user_id, exc)
            return None

    def ensure_for_max_user(
        self,
        max_user_id: str,
        *,
        full_name: str | None = None,
    ) -> dict[str, Any]:
        mid = str(max_user_id).strip()
        existing = self.get_by_max_user_id(mid)
        if existing:
            return existing
        email = f"max_{mid}@clients.sfrfr.local"
        auth_uid = self._ensure_auth_user_for_max(mid, email)
        payload: dict[str, Any] = {
            "max_user_id": mid,
            "email": email,
            "full_name": full_name or f"MAX {mid}",
            "preferred_channel": "max_miniapp",
            "preferred_channel_set_at": datetime.now(UTC).isoformat(),
        }
        if auth_uid:
            payload["user_id"] = auth_uid
        response = self.client.table("clients").insert(payload).execute()
        row = self._one_or_none(response)
        if row:
            return row
        # гонка: параллельный insert
        again = self.get_by_max_user_id(mid)
        if again:
            return again
        raise RuntimeError(f"clients insert returned empty for max_user_id={mid}")

    def set_preferred_channel(self, client_id: str, channel: str) -> dict[str, Any]:
        if channel not in _CHANNELS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="preferred_channel must be max_miniapp|web_cabinet|unset",
            )
        response = (
            self.client.table("clients")
            .update(
                {
                    "preferred_channel": channel,
                    "preferred_channel_set_at": datetime.now(UTC).isoformat(),
                }
            )
            .eq("id", client_id)
            .execute()
        )
        row = self._one_or_none(response)
        if not row:
            raise RuntimeError("clients preferred_channel update returned empty")
        return row

    def link_max_to_user(
        self,
        *,
        user_id: str,
        max_user_id: str,
        email: str | None,
    ) -> dict[str, Any]:
        """Привязать max_user_id к auth-пользователю; конфликт → 409."""
        by_max = self.get_by_max_user_id(max_user_id)
        by_user = self.get_by_user_id(user_id)

        if by_max and by_max.get("user_id") and str(by_max["user_id"]) != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="max_user_id already linked to another client",
            )

        if by_user and by_user.get("max_user_id") and str(by_user["max_user_id"]) != max_user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="client already linked to another max_user_id",
            )

        if by_max and not by_max.get("user_id"):
            # MAX-клиент без веба → привязываем auth
            response = (
                self.client.table("clients")
                .update({"user_id": user_id, "email": email or by_max.get("email")})
                .eq("id", by_max["id"])
                .execute()
            )
            row = self._one_or_none(response)
            if not row:
                raise RuntimeError("clients link update returned empty")
            return row

        client = by_user or self.ensure_for_auth_user(user_id, email=email)
        response = (
            self.client.table("clients")
            .update({"max_user_id": max_user_id})
            .eq("id", client["id"])
            .execute()
        )
        row = self._one_or_none(response)
        if not row:
            raise RuntimeError("clients max link update returned empty")
        return row

    def audit(self, actor_id: str | None, action: str) -> None:
        self.client.table("access_audit").insert(
            {"case_id": None, "actor_id": actor_id, "action": action}
        ).execute()
