"""Серверный репозиторий пенсионных дел в Supabase/Postgres.

Service role намеренно используется только после проверки Principal в API.
RLS остаётся вторым уровнем защиты для browser-клиентов и Storage.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from sfrfr.db.session import get_supabase_client
from sfrfr.security.auth import Principal, StaffRole


class CaseRepository:
    def __init__(self) -> None:
        self.client = get_supabase_client()

    def _client_id(self, user_id: str) -> str | None:
        response = (
            self.client.table("clients")
            .select("id")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        row: dict[str, Any] | None = response.data
        return str(row["id"]) if row else None

    def _case(self, case_id: str) -> dict[str, Any] | None:
        response = (
            self.client.table("cases")
            .select("*, clients(full_name, phone, email), checklist_items(*), documents(*)")
            .eq("id", case_id)
            .maybe_single()
            .execute()
        )
        return response.data

    def can_access(self, principal: Principal, case: dict[str, Any]) -> bool:
        if principal.role in (StaffRole.ADMIN, StaffRole.OPERATOR):
            return True
        if principal.role is StaffRole.EXPERT:
            return str(case.get("expert_user_id")) == principal.user_id

        client_id = self._client_id(principal.user_id)
        if client_id and str(case.get("client_id")) == client_id:
            return True
        representative = (
            self.client.table("case_representatives")
            .select("case_id")
            .eq("case_id", case["id"])
            .eq("user_id", principal.user_id)
            .maybe_single()
            .execute()
        )
        return bool(representative.data)

    def require_case(self, principal: Principal, case_id: str) -> dict[str, Any]:
        case = self._case(case_id)
        if case is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
        if not self.can_access(principal, case):
            # Не раскрываем существование чужого дела.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
        return case

    def list_cases(self, principal: Principal) -> list[dict[str, Any]]:
        query = self.client.table("cases").select(
            "*, clients(full_name, phone, email), checklist_items(id, status, owner)"
        )
        if principal.role in (StaffRole.ADMIN, StaffRole.OPERATOR):
            return query.order("created_at", desc=True).execute().data or []
        if principal.role is StaffRole.EXPERT:
            return (
                query.eq("expert_user_id", principal.user_id)
                .order("created_at", desc=True)
                .execute()
                .data
                or []
            )

        client_id = self._client_id(principal.user_id)
        own = (
            query.eq("client_id", client_id).order("created_at", desc=True).execute().data or []
            if client_id
            else []
        )
        represented = (
            self.client.table("case_representatives")
            .select(
                "cases(*, clients(full_name, phone, email), checklist_items(id, status, owner))"
            )
            .eq("user_id", principal.user_id)
            .execute()
            .data
            or []
        )
        represented_cases = [row["cases"] for row in represented if row.get("cases")]
        by_id = {str(row["id"]): row for row in [*own, *represented_cases]}
        return list(by_id.values())

    def update_case_status(self, case_id: str, status_value: str, actor_id: str) -> dict[str, Any]:
        response = (
            self.client.table("cases")
            .update({"pipeline_status": status_value})
            .eq("id", case_id)
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
        self.audit(case_id, actor_id, "pipeline_status_updated")
        return response.data[0]

    def audit(self, case_id: str, actor_id: str | None, action: str) -> None:
        self.client.table("access_audit").insert(
            {"case_id": case_id, "actor_id": actor_id, "action": action}
        ).execute()

    def has_consent(self, case_id: str) -> bool:
        response = (
            self.client.table("consents")
            .select("id")
            .eq("case_id", case_id)
            .limit(1)
            .execute()
        )
        return bool(response.data)

    def list_consents(self, case_id: str) -> list[dict[str, Any]]:
        return (
            self.client.table("consents")
            .select("*")
            .eq("case_id", case_id)
            .order("accepted_at", desc=True)
            .execute()
            .data
            or []
        )

    def accept_consent(
        self,
        case_id: str,
        *,
        version: str,
        actor_id: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"case_id": case_id, "version": version}
        if ip:
            payload["ip"] = ip
        if user_agent:
            payload["user_agent"] = user_agent
        response = self.client.table("consents").insert(payload).execute()
        self.client.table("cases").update({"b2c_status": "consent_accepted"}).eq(
            "id", case_id
        ).eq("b2c_status", "lead").execute()
        self.audit(case_id, actor_id, "consent_accepted")
        return response.data[0]

    def list_contract_acceptances(self, case_id: str) -> list[dict[str, Any]]:
        return (
            self.client.table("contract_acceptances")
            .select("*")
            .eq("case_id", case_id)
            .order("accepted_at", desc=True)
            .execute()
            .data
            or []
        )

    def accept_contract(
        self,
        case_id: str,
        *,
        offer_version: str,
        actor_id: str,
        order_id: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "case_id": case_id,
            "offer_version": offer_version,
            "acceptance_meta": meta or {},
        }
        if order_id:
            payload["order_id"] = order_id
        response = self.client.table("contract_acceptances").insert(payload).execute()
        self.client.table("cases").update({"b2c_status": "contract_accepted"}).eq(
            "id", case_id
        ).execute()
        self.audit(case_id, actor_id, "contract_accepted")
        return response.data[0]

    def list_orders(self, case_id: str) -> list[dict[str, Any]]:
        return (
            self.client.table("orders")
            .select("*, payments(*)")
            .eq("case_id", case_id)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )

    def get_pipeline_draft(self, case_id: str) -> dict[str, Any] | None:
        row = (
            self.client.table("case_pipeline_data")
            .select("draft")
            .eq("case_id", case_id)
            .maybe_single()
            .execute()
            .data
        )
        if not row:
            return None
        draft = row.get("draft")
        return draft if isinstance(draft, dict) else None

    def get_result_evidence(self, case_id: str) -> dict[str, Any] | None:
        rows = (
            self.client.table("result_evidence")
            .select("*")
            .eq("case_id", case_id)
            .order("confirmed_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None

    def unread_staff_messages(self, case_id: str, user_id: str) -> int:
        last_view = (
            self.client.table("access_audit")
            .select("at")
            .eq("case_id", case_id)
            .eq("actor_id", user_id)
            .eq("action", "case_viewed")
            .order("at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        query = (
            self.client.table("case_messages")
            .select("id", count="exact")
            .eq("case_id", case_id)
            .in_("author_kind", ["staff", "system"])
        )
        if last_view:
            query = query.gt("created_at", last_view[0]["at"])
        response = query.execute()
        if response.count is not None:
            return int(response.count)
        return len(response.data or [])

    @staticmethod
    def next_client_action(case: dict[str, Any]) -> str | None:
        items = case.get("checklist_items") or []
        open_items = [
            item
            for item in items
            if item.get("status") not in ("done", "cancelled")
        ]
        open_items.sort(key=lambda item: (item.get("sort_order") or 0, item.get("title") or ""))
        client_owned = [item for item in open_items if item.get("owner") == "client"]
        chosen = client_owned[0] if client_owned else (open_items[0] if open_items else None)
        return str(chosen["title"]) if chosen and chosen.get("title") else None

    @staticmethod
    def required_document_items(case: dict[str, Any]) -> list[dict[str, Any]]:
        items = case.get("checklist_items") or []
        return [
            item
            for item in items
            if item.get("item_type") == "document"
            and item.get("owner") == "client"
            and item.get("status") not in ("done", "cancelled")
        ]
