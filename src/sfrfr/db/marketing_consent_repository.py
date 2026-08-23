"""Репозиторий журнала marketing_consents."""

from __future__ import annotations

from typing import Any

from sfrfr.db.supabase_client import get_supabase_client
from sfrfr.services.marketing_consent import (
    Channel,
    ConsentStatus,
    contact_key_for_client,
    contact_key_for_email,
    contact_key_for_max,
)


class MarketingConsentRepository:
    def __init__(self, client: Any | None = None) -> None:
        self.client = client or get_supabase_client()

    def list_for_contact(
        self,
        *,
        contact_key: str | None = None,
        max_user_id: str | None = None,
        email: str | None = None,
        client_id: str | None = None,
        limit: int = 40,
    ) -> list[dict[str, Any]]:
        keys: list[str] = []
        if contact_key:
            keys.append(contact_key)
        if max_user_id:
            keys.append(contact_key_for_max(max_user_id))
        if email:
            keys.append(contact_key_for_email(email))
        if client_id:
            keys.append(contact_key_for_client(client_id))
        if not keys:
            return []
        # Один запрос на ключи; сортировка по created_at desc в Python.
        rows: list[dict[str, Any]] = []
        for key in dict.fromkeys(keys):
            resp = (
                self.client.table("marketing_consents")
                .select("*")
                .eq("contact_key", key)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            rows.extend(resp.data or [])
        rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
        return rows[:limit]

    def record_event(
        self,
        *,
        contact_key: str,
        channel: Channel,
        status: ConsentStatus,
        source: str,
        consent_text_version: str,
        proof_id: str | None = None,
        case_id: str | None = None,
        client_id: str | None = None,
        actor_id: str | None = None,
        suppression_reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "contact_key": contact_key,
            "channel": channel,
            "status": status,
            "source": source,
            "consent_text_version": consent_text_version,
            "metadata_json": metadata or {},
        }
        if proof_id:
            payload["proof_id"] = proof_id
        if case_id:
            payload["case_id"] = case_id
        if client_id:
            payload["client_id"] = client_id
        if actor_id:
            payload["actor_id"] = actor_id
        if suppression_reason:
            payload["suppression_reason"] = suppression_reason
        resp = self.client.table("marketing_consents").insert(payload).execute()
        data = resp.data
        if isinstance(data, list) and data:
            return data[0]
        return payload

    def status_summary(
        self,
        *,
        max_user_id: str | None = None,
        email: str | None = None,
        client_id: str | None = None,
    ) -> dict[str, Any]:
        from sfrfr.services.marketing_consent import latest_status

        rows = self.list_for_contact(
            max_user_id=max_user_id, email=email, client_id=client_id
        )
        channels = ("max", "email", "sms")
        by_ch: dict[str, Any] = {}
        for ch in channels:
            st = latest_status(rows, channel=ch)  # type: ignore[arg-type]
            last = next((r for r in rows if str(r.get("channel")) == ch), None)
            by_ch[ch] = {
                "status": st or "none",
                "granted": st == "granted",
                "last_event": last,
            }
        return {"channels": by_ch, "events": rows[:10]}
