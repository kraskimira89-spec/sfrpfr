"""Репозиторий secure_action_links / secure_action_events (Supabase)."""

from __future__ import annotations

from typing import Any, Protocol

from sfrfr.db.session import get_supabase_client


class SecureActionLinksRepo(Protocol):
    def insert_link(self, row: dict[str, Any]) -> dict[str, Any]: ...

    def get_by_hash(self, token_hash: str) -> dict[str, Any] | None: ...

    def get_by_id(self, link_id: str) -> dict[str, Any] | None: ...

    def update_link(self, link_id: str, fields: dict[str, Any]) -> dict[str, Any]: ...

    def list_active_for_case_purpose(
        self, case_id: str, purpose: str
    ) -> list[dict[str, Any]]: ...

    def insert_event(self, row: dict[str, Any]) -> dict[str, Any]: ...


class SecureActionLinksRepository:
    def __init__(self, client: Any | None = None) -> None:
        self.client = client or get_supabase_client()

    def insert_link(self, row: dict[str, Any]) -> dict[str, Any]:
        resp = self.client.table("secure_action_links").insert(row).execute()
        return (resp.data or [row])[0]

    def get_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        resp = (
            self.client.table("secure_action_links")
            .select("*")
            .eq("token_hash", token_hash)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None

    def get_by_id(self, link_id: str) -> dict[str, Any] | None:
        resp = (
            self.client.table("secure_action_links")
            .select("*")
            .eq("id", link_id)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return rows[0] if rows else None

    def update_link(self, link_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        resp = (
            self.client.table("secure_action_links")
            .update(fields)
            .eq("id", link_id)
            .execute()
        )
        return (resp.data or [fields])[0]

    def list_active_for_case_purpose(
        self, case_id: str, purpose: str
    ) -> list[dict[str, Any]]:
        resp = (
            self.client.table("secure_action_links")
            .select("*")
            .eq("case_id", case_id)
            .eq("purpose", purpose)
            .eq("status", "active")
            .order("created_at", desc=True)
            .limit(40)
            .execute()
        )
        return list(resp.data or [])

    def insert_event(self, row: dict[str, Any]) -> dict[str, Any]:
        resp = self.client.table("secure_action_events").insert(row).execute()
        return (resp.data or [row])[0]
