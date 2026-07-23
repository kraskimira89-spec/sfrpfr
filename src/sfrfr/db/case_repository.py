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
            self.client.table("clients").select("id").eq("user_id", user_id).maybe_single().execute()
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
            return query.eq("expert_user_id", principal.user_id).order("created_at", desc=True).execute().data or []

        client_id = self._client_id(principal.user_id)
        own = (
            query.eq("client_id", client_id).order("created_at", desc=True).execute().data or []
            if client_id
            else []
        )
        represented = (
            self.client.table("case_representatives")
            .select("cases(*, clients(full_name, phone, email), checklist_items(id, status, owner))")
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
