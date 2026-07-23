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
        if user_id.startswith("max:"):
            max_uid = user_id.removeprefix("max:")
            response = (
                self.client.table("clients")
                .select("id")
                .eq("max_user_id", max_uid)
                .maybe_single()
                .execute()
            )
            row: dict[str, Any] | None = response.data
            return str(row["id"]) if row else None
        response = (
            self.client.table("clients")
            .select("id")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        row = response.data
        return str(row["id"]) if row else None

    def _client_id_for_principal(self, principal: Principal) -> str | None:
        if principal.max_user_id:
            response = (
                self.client.table("clients")
                .select("id")
                .eq("max_user_id", principal.max_user_id)
                .maybe_single()
                .execute()
            )
            row: dict[str, Any] | None = response.data
            if row:
                return str(row["id"])
        return self._client_id(principal.user_id)

    def _case(self, case_id: str) -> dict[str, Any] | None:
        response = (
            self.client.table("cases")
            .select(
                "*, clients(full_name, phone, email, max_user_id, preferred_channel, "
                "preferred_channel_set_at, user_id), checklist_items(*), documents(*)"
            )
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

        client_id = self._client_id_for_principal(principal)
        if client_id and str(case.get("client_id")) == client_id:
            return True
        if principal.is_max_only:
            return False
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
            "*, clients(full_name, phone, email, max_user_id, preferred_channel, user_id), "
            "checklist_items(id, status, owner), orders(package_code, status)"
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
                "preferred_channel, user_id), checklist_items(id, status, owner))"
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
        row = self.get_pipeline_row(case_id)
        if not row:
            return None
        draft = row.get("draft")
        return draft if isinstance(draft, dict) else None

    def get_pipeline_row(self, case_id: str) -> dict[str, Any] | None:
        return (
            self.client.table("case_pipeline_data")
            .select("findings, draft, error, ocr_texts, updated_at")
            .eq("case_id", case_id)
            .maybe_single()
            .execute()
            .data
        )

    def get_pipeline_findings(self, case_id: str) -> list[dict[str, Any]]:
        row = self.get_pipeline_row(case_id)
        if not row:
            return []
        findings = row.get("findings") or []
        return findings if isinstance(findings, list) else []

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
            .select("id, storage_path, doc_type, created_at")
            .eq("case_id", case_id)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )

    def request_pipeline_run(self, case_id: str, actor_id: str) -> dict[str, Any]:
        """Клиент/сотрудник: запросить проверку (единая семантика ТЗ-09)."""
        case = self._case(case_id)
        if case is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
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
        actor_id: str,
    ) -> dict[str, Any]:
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
        self.audit(case_id, actor_id, f"order_created:{package_code}")
        return response.data[0]

    def get_order(self, case_id: str, order_id: str) -> dict[str, Any] | None:
        return (
            self.client.table("orders")
            .select("*, payments(*)")
            .eq("id", order_id)
            .eq("case_id", case_id)
            .maybe_single()
            .execute()
            .data
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
        if not rows:
            raise HTTPException(status_code=404, detail="payment not found")
        row = rows[0]
        updates: dict[str, Any] = {"status": status_value}
        if fiscal_status is not None:
            updates["fiscal_status"] = fiscal_status
        if paid or status_value in ("succeeded", "paid"):
            updates["paid_at"] = datetime.now(UTC).isoformat()
            updates["status"] = "succeeded"
        response = (
            self.client.table("payments").update(updates).eq("id", row["id"]).execute()
        )
        order = row.get("orders") or {}
        resolved_case_id = str(case_id or order.get("case_id") or "")
        oid = str(order.get("id") or row.get("order_id") or "")
        code = str(package_code or order.get("package_code") or "")
        if (paid or status_value in ("succeeded", "paid")) and oid:
            self.client.table("orders").update({"status": "paid"}).eq("id", oid).execute()
            if resolved_case_id:
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
        return response.data[0] if response.data else row

    def upsert_checklist_item(
        self,
        case_id: str,
        *,
        title: str,
        item_type: str,
        owner: str,
        actor_id: str,
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

    def anonymized_analytics_rows(self) -> list[dict[str, Any]]:
        cases = (
            self.client.table("cases")
            .select(
                "id, segment, region_bucket, pipeline_status, b2c_status, problem_type, "
                "created_at, first_contact_at, orders(package_code, status), "
                "result_evidence(monthly_before_rub, monthly_after_rub, lump_sum_rub), "
                "clients(preferred_channel, max_user_id, user_id)"
            )
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
        rows: list[dict[str, Any]] = []
        for case in cases:
            orders = case.get("orders") or []
            evidence_list = case.get("result_evidence") or []
            evidence = evidence_list[0] if evidence_list else {}
            client = case.get("clients") or {}
            codes = {o.get("package_code") for o in orders}
            paid = {o.get("package_code") for o in orders if o.get("status") == "paid"}
            before = float((evidence or {}).get("monthly_before_rub") or 0)
            after = float((evidence or {}).get("monthly_after_rub") or 0)
            rows.append(
                {
                    "case_id": str(case["id"]),
                    "segment": case.get("segment"),
                    "region_bucket": case.get("region_bucket"),
                    "stage": case.get("b2c_status"),
                    "pipeline": case.get("pipeline_status"),
                    "problem_type": case.get("problem_type"),
                    "created_at": case.get("created_at"),
                    "paid_diag": "DIAG" in paid,
                    "paid_service": "ACCOMP" in paid,
                    "result_band": "up" if after > before else ("flat" if evidence else "unknown"),
                    "sf_due": "SF_LUMP" in codes or "SF_MONTH" in codes,
                    "sf_paid": "SF_LUMP" in paid or "SF_MONTH" in paid,
                    "silent_flag": case.get("b2c_status") == "client_silent_escalation",
                    "preferred_channel": client.get("preferred_channel") or "unset",
                    "max_linked": bool(client.get("max_user_id")),
                    "web_linked": bool(client.get("user_id")),
                }
            )
        return rows
