"""Серверный репозиторий пенсионных дел в Supabase/Postgres.

Service role намеренно используется только после проверки Principal в API.
RLS остаётся вторым уровнем защиты для browser-клиентов и Storage.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from sfrfr.db.session import get_supabase_client
from sfrfr.security.auth import Principal, StaffRole

CURRENT_CONSENT_VERSION = "pdn-consent-2026-08-22"


class CaseRepository:
    def __init__(self) -> None:
        self.client = get_supabase_client()

    @staticmethod
    def _one_or_none(response: Any) -> dict[str, Any] | None:
        """Безопасно вытащить одну строку: пустой maybe_single даёт response=None."""
        if response is None:
            return None
        data = getattr(response, "data", None)
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data:
            return data[0]
        return None

    def _client_id(self, user_id: str) -> str | None:
        if user_id.startswith("max:"):
            max_uid = user_id.removeprefix("max:")
            row = self._one_or_none(
                self.client.table("clients")
                .select("id")
                .eq("max_user_id", max_uid)
                .limit(1)
                .execute()
            )
            return str(row["id"]) if row else None
        row = self._one_or_none(
            self.client.table("clients")
            .select("id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return str(row["id"]) if row else None

    def _client_id_for_principal(self, principal: Principal) -> str | None:
        if principal.max_user_id:
            row = self._one_or_none(
                self.client.table("clients")
                .select("id")
                .eq("max_user_id", principal.max_user_id)
                .limit(1)
                .execute()
            )
            if row:
                return str(row["id"])
        return self._client_id(principal.user_id)

    def _case(self, case_id: str) -> dict[str, Any] | None:
        return self._one_or_none(
            self.client.table("cases")
            .select(
                "*, clients(full_name, phone, email, max_user_id, preferred_channel, "
                "preferred_channel_set_at, user_id), checklist_items(*), documents(*)"
            )
            .eq("id", case_id)
            .limit(1)
            .execute()
        )

    def can_access(self, principal: Principal, case: dict[str, Any]) -> bool:
        if principal.role in (StaffRole.ADMIN, StaffRole.OPERATOR):
            return True
        if principal.role is StaffRole.EXPERT:
            return str(case.get("expert_user_id")) == principal.user_id

        client_id = self._client_id_for_principal(principal)
        if client_id and str(case.get("client_id")) == client_id:
            return True
        if principal.is_max_only:
            return False
        representative = self._one_or_none(
            self.client.table("case_representatives")
            .select("case_id")
            .eq("case_id", case["id"])
            .eq("user_id", principal.user_id)
            .limit(1)
            .execute()
        )
        return bool(representative)

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
            "*, clients(full_name, phone, email, max_user_id, preferred_channel, user_id), "
            "checklist_items(id, status, owner, title, item_type, due_at), "
            "orders(package_code, status, amount_rub, created_at)"
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

        client_id = self._client_id_for_principal(principal)
        own = (
            query.eq("client_id", client_id).order("created_at", desc=True).execute().data or []
            if client_id
            else []
        )
        if principal.is_max_only:
            return own
        represented = (
            self.client.table("case_representatives")
            .select(
                "cases(*, clients(full_name, phone, email, max_user_id, "
                "preferred_channel, user_id), "
                "checklist_items(id, status, owner, title, item_type, due_at))"
            )
            .eq("user_id", principal.user_id)
            .execute()
            .data
            or []
        )
        represented_cases = [row["cases"] for row in represented if row.get("cases")]
        by_id = {str(row["id"]): row for row in [*own, *represented_cases]}
        return list(by_id.values())

    def get_case_row(self, case_id: str) -> dict[str, Any] | None:
        return self._case(case_id)

    def update_case_status(
        self,
        case_id: str,
        status_value: str,
        actor_id: str | None,
        *,
        notify: bool = True,
    ) -> dict[str, Any]:
        previous = self._case(case_id)
        prev_status = str(previous.get("pipeline_status") or "") if previous else ""
        response = (
            self.client.table("cases")
            .update({"pipeline_status": status_value})
            .eq("id", case_id)
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
        self.audit(case_id, actor_id, "pipeline_status_updated")
        updated = response.data[0]
        if notify and prev_status != status_value:
            try:
                from sfrfr.integrations.client_channels.notifications import (
                    notify_case_status_change,
                )

                client_row: dict[str, Any] = {}
                client_id = updated.get("client_id") or (previous or {}).get("client_id")
                if client_id:
                    client_resp = (
                        self.client.table("clients")
                        .select("email, max_user_id, preferred_channel")
                        .eq("id", client_id)
                        .limit(1)
                        .execute()
                    )
                    rows = client_resp.data or []
                    if rows:
                        client_row = rows[0]
                notify_case_status_change(
                    case_id=case_id,
                    status_value=status_value,
                    previous_status=prev_status or None,
                    client=client_row,
                )
            except Exception:  # noqa: BLE001 — смена статуса важнее доставки
                pass
        return updated

    def audit(self, case_id: str, actor_id: str | None, action: str) -> None:
        self.client.table("access_audit").insert(
            {"case_id": case_id, "actor_id": actor_id, "action": action}
        ).execute()

    def list_representatives(self, case_id: str) -> list[dict[str, Any]]:
        rows = (
            self.client.table("case_representatives")
            .select("case_id, user_id, created_at")
            .eq("case_id", case_id)
            .execute()
            .data
            or []
        )
        result: list[dict[str, Any]] = []
        for row in rows:
            user_id = str(row["user_id"])
            client = self._one_or_none(
                self.client.table("clients")
                .select("id, full_name, email, phone, user_id")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            result.append(
                {
                    "user_id": user_id,
                    "case_id": str(row["case_id"]),
                    "created_at": row.get("created_at"),
                    "full_name": (client or {}).get("full_name"),
                    "email": (client or {}).get("email"),
                    "phone": (client or {}).get("phone"),
                }
            )
        return result

    def add_representative(
        self,
        case_id: str,
        *,
        actor_id: str,
        user_id: str | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        """Выдать доступ законному представителю (только staff через API)."""
        resolved_user_id = user_id
        if not resolved_user_id and email:
            client = self._one_or_none(
                self.client.table("clients")
                .select("user_id, email")
                .ilike("email", email.strip())
                .limit(1)
                .execute()
            )
            if not client or not client.get("user_id"):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="client with this email has no web account yet",
                )
            resolved_user_id = str(client["user_id"])
        if not resolved_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_id or email required",
            )
        existing = self._one_or_none(
            self.client.table("case_representatives")
            .select("case_id, user_id")
            .eq("case_id", case_id)
            .eq("user_id", resolved_user_id)
            .limit(1)
            .execute()
        )
        if existing:
            return {
                "case_id": case_id,
                "user_id": resolved_user_id,
                "already": True,
            }
        self.client.table("case_representatives").insert(
            {"case_id": case_id, "user_id": resolved_user_id}
        ).execute()
        self.audit(case_id, actor_id, f"representative_added:{resolved_user_id[:8]}")
        return {"case_id": case_id, "user_id": resolved_user_id, "already": False}

    def remove_representative(
        self, case_id: str, *, user_id: str, actor_id: str
    ) -> dict[str, Any]:
        self.client.table("case_representatives").delete().eq("case_id", case_id).eq(
            "user_id", user_id
        ).execute()
        self.audit(case_id, actor_id, f"representative_removed:{user_id[:8]}")
        return {"ok": True, "case_id": case_id, "user_id": user_id}

    def is_representative(self, principal: Principal, case_id: str) -> bool:
        if principal.is_max_only or not principal.user_id:
            return False
        return bool(
            self._one_or_none(
                self.client.table("case_representatives")
                .select("case_id")
                .eq("case_id", case_id)
                .eq("user_id", principal.user_id)
                .limit(1)
                .execute()
            )
        )

    def create_case_for_client(
        self,
        *,
        client_id: str,
        actor_id: str | None,
        problem_type: str | None = None,
        seed_checklist: bool = True,
    ) -> dict[str, Any]:
        """Создать дело для клиента (веб / MAX) в Supabase."""
        response = (
            self.client.table("cases")
            .insert(
                {
                    "client_id": client_id,
                    "pipeline_status": "intake",
                    "b2c_status": "lead",
                    "segment": "b2c",
                    "problem_type": problem_type or "client_open",
                }
            )
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=502, detail="failed to create case")
        case = response.data[0]
        case_id = str(case["id"])
        if seed_checklist:
            for idx, title in enumerate(
                ("Выписка ИЛС", "Трудовая книжка / сведения о стаже")
            ):
                self.client.table("checklist_items").insert(
                    {
                        "case_id": case_id,
                        "title": title,
                        "item_type": "document",
                        "owner": "client",
                        "status": "open",
                        "sort_order": idx,
                    }
                ).execute()
        self.audit(case_id, actor_id, "case_created")
        return case

    def has_consent(self, case_id: str) -> bool:
        response = (
            self.client.table("consents")
            .select("id")
            .eq("case_id", case_id)
            .eq("version", CURRENT_CONSENT_VERSION)
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
        try:
            from sfrfr.services.finance_automation import ensure_agreement_draft_invoice

            ensure_agreement_draft_invoice(self, case_id, actor_id)
        except Exception:  # noqa: BLE001 — соглашение важнее черновика счёта
            pass
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
        row = self.get_pipeline_row(case_id)
        if not row:
            return None
        draft = row.get("draft")
        return draft if isinstance(draft, dict) else None

    def get_pipeline_row(self, case_id: str) -> dict[str, Any] | None:
        return self._one_or_none(
            self.client.table("case_pipeline_data")
            .select(
                "findings, draft, error, ocr_texts, analysis_notes, "
                "ils_periods, labor_periods, classifications, updated_at"
            )
            .eq("case_id", case_id)
            .limit(1)
            .execute()
        )

    def get_pipeline_findings(self, case_id: str) -> list[dict[str, Any]]:
        row = self.get_pipeline_row(case_id)
        if not row:
            return []
        findings = row.get("findings") or []
        return findings if isinstance(findings, list) else []

    def get_pipeline_analysis_notes(self, case_id: str) -> str | None:
        row = self.get_pipeline_row(case_id)
        if not row:
            return None
        notes = row.get("analysis_notes")
        return str(notes) if notes else None

    def save_pipeline_snapshot(self, case_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Upsert результатов пайплайна (в т.ч. analysis_notes) в case_pipeline_data."""
        payload: dict[str, Any] = {
            "case_id": case_id,
            "ocr_texts": snapshot.get("ocr_texts") if snapshot.get("ocr_texts") is not None else [],
            "classifications": snapshot.get("classifications")
            if snapshot.get("classifications") is not None
            else [],
            "ils_periods": snapshot.get("ils_periods")
            if snapshot.get("ils_periods") is not None
            else [],
            "labor_periods": snapshot.get("labor_periods")
            if snapshot.get("labor_periods") is not None
            else [],
            "findings": snapshot.get("findings") if snapshot.get("findings") is not None else [],
            "analysis_notes": snapshot.get("analysis_notes"),
            "draft": snapshot.get("draft"),
            "error": snapshot.get("error"),
        }
        response = (
            self.client.table("case_pipeline_data")
            .upsert(payload, on_conflict="case_id")
            .execute()
        )
        data = getattr(response, "data", None)
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict):
            return data
        return payload

    @staticmethod
    def snapshot_from_case_context(ctx: Any) -> dict[str, Any]:
        """Собрать payload из CaseContext (локальный оркестратор)."""
        return {
            "ocr_texts": list(getattr(ctx, "ocr_texts", None) or []),
            "classifications": [
                c.model_dump(mode="json") if hasattr(c, "model_dump") else c
                for c in (getattr(ctx, "classifications", None) or [])
            ],
            "ils_periods": list(getattr(ctx, "ils_periods", None) or []),
            "labor_periods": list(getattr(ctx, "labor_periods", None) or []),
            "findings": [
                f.model_dump(mode="json") if hasattr(f, "model_dump") else f
                for f in (getattr(ctx, "findings", None) or [])
            ],
            "analysis_notes": getattr(ctx, "analysis_notes", None),
            "draft": (
                ctx.draft.model_dump(mode="json")
                if getattr(ctx, "draft", None) is not None and hasattr(ctx.draft, "model_dump")
                else getattr(ctx, "draft", None)
            ),
            "error": getattr(ctx, "error", None),
        }

    def list_checklist(self, case_id: str) -> list[dict[str, Any]]:
        return (
            self.client.table("checklist_items")
            .select("*")
            .eq("case_id", case_id)
            .order("sort_order")
            .execute()
            .data
            or []
        )

    def list_documents(self, case_id: str) -> list[dict[str, Any]]:
        return (
            self.client.table("documents")
            .select("id, storage_path, doc_type, created_at, content_preview")
            .eq("case_id", case_id)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )

    def request_pipeline_run(self, case_id: str, actor_id: str) -> dict[str, Any]:
        """Клиент/сотрудник: запросить проверку (единая семантика ТЗ-09)."""
        from sfrfr.services.message_dedupe import required_docs_missing

        case = self._case(case_id)
        if case is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
        missing = required_docs_missing(case)
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Для диагностики не хватает: {', '.join(missing)}",
            )
        docs = case.get("documents") or []
        status_now = case.get("pipeline_status") or "intake"
        message = "Проверка запрошена. Специалист и пайплайн уведомлены."
        if docs and status_now == "intake":
            self.update_case_status(case_id, "documents_received", actor_id)
            message = "Документы приняты, проверка запрошена."
        elif status_now in ("documents_received", "ocr_done", "classified", "extracted", "audited"):
            # Клиентский запрос продвигает к human_review, если ещё не там.
            if status_now != "human_review":
                self.update_case_status(case_id, "human_review", actor_id)
                message = "Дело передано на проверку специалисту."
        self.audit(case_id, actor_id, "pipeline_run_requested")
        refreshed = self._case(case_id) or case
        return {
            "ok": True,
            "message": message,
            "pipeline_status": refreshed.get("pipeline_status"),
            "findings": self.get_pipeline_findings(case_id),
            "analysis_notes": self.get_pipeline_analysis_notes(case_id),
            "draft": self.get_pipeline_draft(case_id),
        }

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

    def list_audit(self, case_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        return (
            self.client.table("access_audit")
            .select("*")
            .eq("case_id", case_id)
            .order("at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )

    def list_all_orders(self) -> list[dict[str, Any]]:
        return (
            self.client.table("orders")
            .select("*, payments(*), cases(id, b2c_status, pipeline_status)")
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )

    def create_order(
        self,
        case_id: str,
        *,
        package_code: str,
        amount_rub: float,
        status_value: str,
        actor_id: str | None = None,
        due_at: str | None = None,
        service_label: str | None = None,
        invoice_status: str | None = None,
    ) -> dict[str, Any]:
        from sfrfr.services.staff_finance import invoice_number_from_id

        response = (
            self.client.table("orders")
            .insert(
                {
                    "case_id": case_id,
                    "package_code": package_code,
                    "amount_rub": amount_rub,
                    "status": status_value,
                }
            )
            .execute()
        )
        row = response.data[0]
        oid = str(row.get("id") or "")
        extra: dict[str, Any] = {}
        if oid:
            extra["invoice_number"] = invoice_number_from_id(oid)
        if due_at:
            extra["due_at"] = due_at
        if service_label:
            extra["service_label"] = service_label
        if invoice_status:
            extra["invoice_status"] = invoice_status
        elif status_value == "draft":
            extra["invoice_status"] = "draft"
        if extra and oid:
            try:
                updated = self.client.table("orders").update(extra).eq("id", oid).execute()
                if updated.data:
                    row = updated.data[0]
            except Exception:  # noqa: BLE001 — колонки finance появятся после миграции
                pass
        self.audit(case_id, actor_id, f"order_created:{package_code}")
        try:
            self.append_finance_audit(
                order_id=oid,
                case_id=case_id,
                actor_id=actor_id,
                action="order_created",
                payload={
                    "package_code": package_code,
                    "amount_rub": amount_rub,
                    "status": status_value,
                },
            )
        except Exception:  # noqa: BLE001
            pass
        return row

    def get_order_by_id(self, order_id: str) -> dict[str, Any] | None:
        return self._one_or_none(
            self.client.table("orders")
            .select("*, payments(*)")
            .eq("id", order_id)
            .limit(1)
            .execute()
        )

    def update_order_fields(
        self,
        order_id: str,
        *,
        case_id: str,
        actor_id: str | None,
        action: str,
        fields: dict[str, Any],
        audit_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self.client.table("orders").update(fields).eq("id", order_id).execute()
        row = response.data[0] if response.data else {"id": order_id, **fields}
        self.audit(case_id, actor_id, action)
        self.append_finance_audit(
            order_id=order_id,
            case_id=case_id,
            actor_id=actor_id,
            action=action,
            payload=audit_payload or fields,
        )
        return row

    def append_finance_audit(
        self,
        *,
        order_id: str,
        case_id: str,
        actor_id: str | None,
        action: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.client.table("finance_audit").insert(
            {
                "order_id": order_id,
                "case_id": case_id,
                "actor_id": actor_id,
                "action": action,
                "payload": payload or {},
            }
        ).execute()

    def list_finance_audit(self, order_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        return (
            self.client.table("finance_audit")
            .select("id, action, payload, actor_id, at")
            .eq("order_id", order_id)
            .order("at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )

    def get_order(self, case_id: str, order_id: str) -> dict[str, Any] | None:
        return self._one_or_none(
            self.client.table("orders")
            .select("*, payments(*)")
            .eq("id", order_id)
            .eq("case_id", case_id)
            .limit(1)
            .execute()
        )

    def create_payment_record(
        self,
        *,
        order_id: str,
        case_id: str,
        provider: str,
        provider_payment_id: str,
        status_value: str,
        actor_id: str | None,
        fiscal_status: str | None = None,
    ) -> dict[str, Any]:
        response = (
            self.client.table("payments")
            .insert(
                {
                    "order_id": order_id,
                    "provider": provider,
                    "provider_payment_id": provider_payment_id,
                    "status": status_value,
                    "fiscal_status": fiscal_status,
                }
            )
            .execute()
        )
        self.audit(case_id, actor_id, f"payment_created:{provider}")
        return response.data[0]

    def apply_provider_payment(
        self,
        *,
        provider_payment_id: str,
        status_value: str,
        order_id: str | None = None,
        paid: bool = False,
        fiscal_status: str | None = None,
        package_code: str | None = None,
        case_id: str | None = None,
    ) -> dict[str, Any]:
        """Обновить платёж по webhook провайдера; при paid — статус заказа и b2c."""
        from datetime import UTC, datetime

        query = (
            self.client.table("payments")
            .select("*, orders(id, case_id, status, package_code)")
            .eq("provider_payment_id", provider_payment_id)
        )
        if order_id:
            query = query.eq("order_id", order_id)
        rows = query.limit(1).execute().data or []
        if not rows and order_id:
            order_row = self.get_order_by_id(order_id)
            if order_row:
                resolved = str(case_id or order_row.get("case_id") or "")
                self.create_payment_record(
                    order_id=order_id,
                    case_id=resolved,
                    provider="yookassa",
                    provider_payment_id=provider_payment_id,
                    status_value="pending",
                    actor_id=None,
                )
                rows = query.limit(1).execute().data or []
        if not rows:
            raise HTTPException(status_code=404, detail="payment not found")
        row = rows[0]
        already_paid = str(row.get("status") or "") in ("succeeded", "paid")
        marking_paid = bool(paid or status_value in ("succeeded", "paid"))
        newly_paid = marking_paid and not already_paid
        updates: dict[str, Any] = {"status": status_value}
        if fiscal_status is not None:
            updates["fiscal_status"] = fiscal_status
        if marking_paid:
            updates["paid_at"] = datetime.now(UTC).isoformat()
            updates["status"] = "succeeded"
        response = (
            self.client.table("payments").update(updates).eq("id", row["id"]).execute()
        )
        order = row.get("orders") or {}
        resolved_case_id = str(case_id or order.get("case_id") or "")
        oid = str(order.get("id") or row.get("order_id") or "")
        code = str(package_code or order.get("package_code") or "")
        if marking_paid and oid:
            self.client.table("orders").update({"status": "paid"}).eq("id", oid).execute()
            if resolved_case_id and newly_paid:
                self.audit(resolved_case_id, None, f"payment_succeeded:{provider_payment_id}")
                b2c = None
                if code == "DIAG":
                    b2c = "diagnostic_paid"
                elif code == "ACCOMP":
                    b2c = "service_paid"
                elif code in ("SF_LUMP", "SF_MONTH"):
                    b2c = "success_fee_paid"
                if b2c:
                    self.client.table("cases").update({"b2c_status": b2c}).eq(
                        "id", resolved_case_id
                    ).execute()
                try:
                    from sfrfr.services.finance_automation import on_order_fully_paid

                    on_order_fully_paid(
                        self, resolved_case_id, code, actor_id=None
                    )
                except Exception:  # noqa: BLE001 — оплата уже учтена
                    pass
        payment_out = response.data[0] if response.data else row
        return {
            "payment": payment_out,
            "newly_paid": newly_paid,
            "case_id": resolved_case_id,
            "order_id": oid,
            "package_code": code,
            "provider_payment_id": provider_payment_id,
        }

    def upsert_checklist_item(
        self,
        case_id: str,
        *,
        title: str,
        item_type: str,
        owner: str,
        actor_id: str | None = None,
        due_at: str | None = None,
        note: str | None = None,
        sort_order: int = 0,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "case_id": case_id,
            "title": title,
            "item_type": item_type,
            "owner": owner,
            "sort_order": sort_order,
            "status": "open",
        }
        if due_at:
            payload["due_at"] = due_at
        if note:
            payload["note"] = note
        response = self.client.table("checklist_items").insert(payload).execute()
        self.audit(case_id, actor_id, "checklist_item_created")
        return response.data[0]

    def update_checklist_item(
        self,
        case_id: str,
        item_id: str,
        *,
        actor_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        response = (
            self.client.table("checklist_items")
            .update(updates)
            .eq("id", item_id)
            .eq("case_id", case_id)
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="checklist item not found")
        self.audit(case_id, actor_id, "checklist_item_updated")
        return response.data[0]

    def update_next_action(
        self,
        case_id: str,
        actor_id: str | None,
        *,
        next_action: str | None = None,
        next_action_at: str | None = None,
        waiting_on: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if next_action is not None:
            payload["next_action"] = next_action.strip() or None
        if next_action_at is not None:
            payload["next_action_at"] = next_action_at or None
        if waiting_on is not None:
            payload["waiting_on"] = waiting_on
        if not payload:
            case = self._case(case_id)
            if case is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
            return case
        response = (
            self.client.table("cases").update(payload).eq("id", case_id).execute()
        )
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
        self.audit(case_id, actor_id, "next_action_updated")
        return response.data[0]

    def update_archive_prep(
        self,
        case_id: str,
        actor_id: str | None,
        *,
        archive_prep_status: str | None = None,
        archive_tariff: str | None = None,
        archive_successor: str | None = None,
        archive_target: str | None = None,
        archive_followup_at: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if archive_prep_status is not None:
            payload["archive_prep_status"] = archive_prep_status.strip() or None
        if archive_tariff is not None:
            payload["archive_tariff"] = archive_tariff.strip() or None
        if archive_successor is not None:
            payload["archive_successor"] = archive_successor.strip() or None
        if archive_target is not None:
            payload["archive_target"] = archive_target.strip() or None
        if archive_followup_at is not None:
            payload["archive_followup_at"] = archive_followup_at or None
        if not payload:
            case = self._case(case_id)
            if case is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
            return case
        response = (
            self.client.table("cases").update(payload).eq("id", case_id).execute()
        )
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
        self.audit(case_id, actor_id, "archive_prep_updated")
        return response.data[0]

    def update_case_flags(
        self,
        case_id: str,
        actor_id: str,
        *,
        is_test: bool,
    ) -> dict[str, Any]:
        response = (
            self.client.table("cases")
            .update({"is_test": is_test})
            .eq("id", case_id)
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
        self.audit(case_id, actor_id, f"is_test:{is_test}")
        return response.data[0]

    def assign_expert(
        self, case_id: str, expert_user_id: str | None, actor_id: str
    ) -> dict[str, Any]:
        response = (
            self.client.table("cases")
            .update({"expert_user_id": expert_user_id})
            .eq("id", case_id)
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="case not found")
        self.audit(case_id, actor_id, "expert_assigned")
        return response.data[0]

    def confirm_result(
        self,
        case_id: str,
        *,
        actor_id: str,
        monthly_before_rub: float,
        monthly_after_rub: float,
        lump_sum_rub: float,
        result_effective_at: str | None,
    ) -> dict[str, Any]:
        from datetime import UTC, datetime

        existing = self.get_result_evidence(case_id)
        payload: dict[str, Any] = {
            "case_id": case_id,
            "monthly_before_rub": monthly_before_rub,
            "monthly_after_rub": monthly_after_rub,
            "lump_sum_rub": lump_sum_rub,
            "confirmed_by": actor_id,
            "confirmed_at": datetime.now(UTC).isoformat(),
        }
        if result_effective_at:
            payload["result_effective_at"] = result_effective_at
        if existing:
            response = (
                self.client.table("result_evidence")
                .update(payload)
                .eq("id", existing["id"])
                .execute()
            )
        else:
            response = self.client.table("result_evidence").insert(payload).execute()
        self.client.table("cases").update({"b2c_status": "result_confirmed"}).eq(
            "id", case_id
        ).execute()
        self.audit(case_id, actor_id, "result_confirmed")
        return response.data[0]

    def save_knowledge_feedback(
        self,
        case_id: str,
        *,
        actor_id: str,
        what_worked: str | None,
        documents_note: str | None,
        sfr_outcome: str | None,
        quality: str,
    ) -> dict[str, Any]:
        response = (
            self.client.table("case_knowledge_feedback")
            .insert(
                {
                    "case_id": case_id,
                    "author_user_id": actor_id,
                    "what_worked": what_worked,
                    "documents_note": documents_note,
                    "sfr_outcome": sfr_outcome,
                    "quality": quality,
                }
            )
            .execute()
        )
        self.audit(case_id, actor_id, f"knowledge_feedback:{quality}")
        return response.data[0]

    def list_staff_roles(self) -> list[dict[str, Any]]:
        return (
            self.client.table("staff_roles").select("*").order("created_at").execute().data or []
        )

    def upsert_staff_role(self, user_id: str, role: str, actor_id: str) -> dict[str, Any]:
        response = (
            self.client.table("staff_roles")
            .upsert({"user_id": user_id, "role": role})
            .execute()
        )
        self.audit(user_id, actor_id, f"staff_role_upsert:{role}")
        return response.data[0]

    def list_analytics_cases(self, principal: Principal) -> list[dict[str, Any]]:
        """Дела для аналитики без ПДн клиента (только агрегаты на сервере)."""
        # paid_at живёт в payments: embed orders.paid_at роняет PostgREST (колонки нет).
        select_full = (
            "id, pipeline_status, b2c_status, segment, region_bucket, problem_type, "
            "created_at, first_contact_at, expert_user_id, "
            "clients(preferred_channel, max_user_id, user_id), "
            "checklist_items(id), documents(id), consents(id), "
            "orders(package_code, status, amount_rub, created_at), "
            "result_evidence(monthly_before_rub, monthly_after_rub, lump_sum_rub)"
        )
        select_min = (
            "id, pipeline_status, b2c_status, segment, region_bucket, problem_type, "
            "created_at, first_contact_at, expert_user_id, "
            "clients(preferred_channel, max_user_id, user_id), "
            "orders(package_code, status, amount_rub, created_at)"
        )
        query = self.client.table("cases").select(select_full)
        if principal.role is StaffRole.EXPERT:
            query = query.eq("expert_user_id", principal.user_id)
        try:
            return query.order("created_at", desc=True).execute().data or []
        except Exception:  # noqa: BLE001 — запасной select без consents/result_evidence
            query = self.client.table("cases").select(select_min)
            if principal.role is StaffRole.EXPERT:
                query = query.eq("expert_user_id", principal.user_id)
            return query.order("created_at", desc=True).execute().data or []

    def anonymized_analytics_rows(self) -> list[dict[str, Any]]:
        """Legacy export rows (service role, все дела)."""
        from sfrfr.services.admin_analytics import case_to_analytics_row

        cases = (
            self.client.table("cases")
            .select(
                "id, pipeline_status, b2c_status, segment, region_bucket, problem_type, "
                "created_at, first_contact_at, expert_user_id, "
                "clients(preferred_channel, max_user_id, user_id), "
                "checklist_items(id), documents(id), consents(id), "
                "orders(package_code, status, amount_rub), "
                "result_evidence(monthly_before_rub, monthly_after_rub, lump_sum_rub)"
            )
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
        return [case_to_analytics_row(case) for case in cases]

