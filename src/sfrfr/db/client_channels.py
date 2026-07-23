"""Клиентский профиль: каналы MAX / веб-кабинет."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status

from sfrfr.db.session import get_supabase_client

_CHANNELS = frozenset({"max_miniapp", "web_cabinet", "unset"})


class ClientChannelRepository:
    def __init__(self) -> None:
        self.client = get_supabase_client()

    def get_by_user_id(self, user_id: str) -> dict[str, Any] | None:
        return (
            self.client.table("clients")
            .select("*")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
            .data
        )

    def get_by_max_user_id(self, max_user_id: str) -> dict[str, Any] | None:
        return (
            self.client.table("clients")
            .select("*")
            .eq("max_user_id", max_user_id)
            .maybe_single()
            .execute()
            .data
        )

    def ensure_for_auth_user(
        self,
        user_id: str,
        *,
        email: str | None = None,
        full_name: str = "Клиент",
    ) -> dict[str, Any]:
        existing = self.get_by_user_id(user_id)
        if existing:
            return existing
        payload: dict[str, Any] = {
            "user_id": user_id,
            "full_name": full_name,
            "preferred_channel": "unset",
        }
        if email:
            payload["email"] = email
        response = self.client.table("clients").insert(payload).execute()
        return response.data[0]

    def ensure_for_max_user(
        self,
        max_user_id: str,
        *,
        full_name: str | None = None,
    ) -> dict[str, Any]:
        existing = self.get_by_max_user_id(max_user_id)
        if existing:
            return existing
        response = (
            self.client.table("clients")
            .insert(
                {
                    "max_user_id": max_user_id,
                    "full_name": full_name or f"MAX {max_user_id}",
                    "preferred_channel": "max_miniapp",
                    "preferred_channel_set_at": datetime.now(UTC).isoformat(),
                }
            )
            .execute()
        )
        return response.data[0]

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
        return response.data[0]

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
            return response.data[0]

        client = by_user or self.ensure_for_auth_user(user_id, email=email)
        response = (
            self.client.table("clients")
            .update({"max_user_id": max_user_id})
            .eq("id", client["id"])
            .execute()
        )
        return response.data[0]

    def audit(self, actor_id: str | None, action: str) -> None:
        self.client.table("access_audit").insert(
            {"case_id": None, "actor_id": actor_id, "action": action}
        ).execute()
