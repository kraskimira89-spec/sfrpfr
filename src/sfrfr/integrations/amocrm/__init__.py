"""Интеграция amoCRM API v4: контакт + сделка, custom fields, без файлов."""

from __future__ import annotations

from typing import Any

import httpx

from sfrfr.core.config import get_settings
from sfrfr.integrations.amocrm.fields import LEAD_FIELD_SPECS, build_lead_custom_fields
from sfrfr.integrations.amocrm.pipeline_stages import (
    AMO_STAGE_NAMES,
    key_for_status_id,
    resolve_status_id_by_name,
    should_move_forward,
    suggest_amo_stage_key,
)
from sfrfr.integrations.amocrm.task_templates import (
    TASK_DOCS_AFTER_DIAG,
    TASK_FIRST_CONTACT,
    TASK_REVIEW_REMINDER,
)


class AmoCrmClient:
    """
    Исходящий sync в amoCRM.
    ПДн-сканы / OCR / СНИЛС не передаём — только case_id, этап и минимальный контакт.
    """

    def __init__(
        self,
        *,
        subdomain: str | None = None,
        access_token: str | None = None,
        pipeline_id: int | None = None,
        status_id: int | None = None,
    ) -> None:
        settings = get_settings()
        self.subdomain = (subdomain if subdomain is not None else settings.amo_subdomain).strip()
        self.access_token = (
            access_token if access_token is not None else settings.amo_access_token
        ).strip()
        pid = pipeline_id if pipeline_id is not None else settings.amo_pipeline_id
        sid = status_id if status_id is not None else settings.amo_status_id
        self.pipeline_id = int(pid) if pid not in (None, "", 0, "0") else None
        self.status_id = int(sid) if sid not in (None, "", 0, "0") else None
        self._pipeline_statuses_cache: list[dict[str, Any]] | None = None

    @property
    def available(self) -> bool:
        return bool(self.subdomain and self.access_token)

    @property
    def base_url(self) -> str:
        return f"https://{self.subdomain}.amocrm.ru/api/v4"

    def lead_url(self, lead_id: str | int) -> str:
        settings = get_settings()
        template = settings.amo_case_url_template or (
            "https://{subdomain}.amocrm.ru/leads/detail/{id}"
        )
        return (
            template.replace("{subdomain}", self.subdomain)
            .replace("{id}", str(lead_id))
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=25.0) as client:
                response = client.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=json_body,
                    params=params,
                )
            body: Any
            try:
                body = response.json() if response.content else {}
            except Exception:  # noqa: BLE001
                body = {"text": response.text[:300]}
            ok = 200 <= response.status_code < 300
            return {
                "ok": ok,
                "status_code": response.status_code,
                "response": body,
            }
        except Exception as exc:  # noqa: BLE001 - не блокируем дело
            return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}

    def list_lead_custom_fields(self) -> dict[str, Any]:
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "no AMO credentials"}
        return self._request("GET", "/leads/custom_fields", params={"limit": 250})

    def list_pipeline_statuses(self, *, force: bool = False) -> list[dict[str, Any]]:
        if not self.available or self.pipeline_id is None:
            return []
        if self._pipeline_statuses_cache is not None and not force:
            return self._pipeline_statuses_cache
        result = self._request("GET", f"/leads/pipelines/{self.pipeline_id}")
        if not result.get("ok"):
            return []
        body = result.get("response") or {}
        statuses = (body.get("_embedded") or {}).get("statuses") or []
        self._pipeline_statuses_cache = statuses if isinstance(statuses, list) else []
        return self._pipeline_statuses_cache

    def resolve_stage_status_id(self, stage_key: str | None) -> int | None:
        if not stage_key:
            return None
        name = AMO_STAGE_NAMES.get(stage_key) or stage_key
        return resolve_status_id_by_name(self.list_pipeline_statuses(), name)

    def create_lead_task(
        self,
        lead_id: str | int,
        text: str,
        *,
        complete_till_hours: int = 24,
        task_type_id: int = 1,
    ) -> dict[str, Any]:
        """Создать задачу по сделке (тип 1 = звонок/контакт)."""
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "no AMO credentials"}
        body = (text or "").strip()
        if not body:
            return {"ok": False, "skipped": True, "reason": "empty task"}
        import time

        complete_till = int(time.time()) + max(1, complete_till_hours) * 3600
        payload = [
            {
                "task_type_id": int(task_type_id),
                "text": body[:5000],
                "complete_till": complete_till,
                "entity_id": int(lead_id),
                "entity_type": "leads",
            }
        ]
        result = self._request("POST", "/tasks", json_body=payload)
        result["lead_id"] = str(lead_id)
        result["action"] = "task"
        return result

    def ensure_lead_fields(self) -> dict[str, Any]:
        """Создать недостающие поля и синхронизировать русские названия / is_api_only."""
        listed = self.list_lead_custom_fields()
        if listed.get("skipped") or not listed.get("ok"):
            return listed
        existing_items = (
            (listed.get("response") or {}).get("_embedded", {}).get("custom_fields", [])
        )
        by_code: dict[str, dict[str, Any]] = {
            str(item.get("code") or "").upper(): item
            for item in existing_items
            if item.get("code")
        }
        existing = set(by_code)
        to_create: list[dict[str, Any]] = []
        for spec in LEAD_FIELD_SPECS:
            if spec["code"].upper() in existing:
                continue
            body: dict[str, Any] = {
                "name": spec["name"],
                "type": spec["type"],
                "code": spec["code"],
            }
            if spec.get("is_api_only"):
                body["is_api_only"] = True
            to_create.append(body)

        created: dict[str, Any] = {"ok": True, "created": [], "existing": sorted(existing)}
        if to_create:
            created = self._request("POST", "/leads/custom_fields", json_body=to_create)
            created["requested"] = [f["code"] for f in to_create]
            if not created.get("ok"):
                return created
            # перечитать после создания
            listed = self.list_lead_custom_fields()
            if listed.get("ok"):
                existing_items = (
                    (listed.get("response") or {})
                    .get("_embedded", {})
                    .get("custom_fields", [])
                )
                by_code = {
                    str(item.get("code") or "").upper(): item
                    for item in existing_items
                    if item.get("code")
                }

        to_patch: list[dict[str, Any]] = []
        skipped_locked: list[str] = []
        for spec in LEAD_FIELD_SPECS:
            item = by_code.get(spec["code"].upper())
            if not item or not item.get("id"):
                continue
            # Системные tracking_data / predefined — имя менять нельзя
            if (
                spec.get("skip_label_sync")
                or item.get("is_predefined")
                or item.get("type") == "tracking_data"
            ):
                skipped_locked.append(spec["code"])
                continue
            want_api_only = bool(spec.get("is_api_only"))
            cur_name = str(item.get("name") or "")
            cur_api_only = bool(item.get("is_api_only"))
            if cur_name == spec["name"] and cur_api_only == want_api_only:
                continue
            to_patch.append(
                {
                    "id": int(item["id"]),
                    "name": spec["name"],
                    "is_api_only": want_api_only,
                }
            )

        patched_codes: list[str] = []
        if to_patch:
            id_to_code = {
                int(item["id"]): code
                for code, item in by_code.items()
                if item.get("id") is not None
            }
            patched_codes = [id_to_code.get(p["id"], str(p["id"])) for p in to_patch]
            patched = self._request("PATCH", "/leads/custom_fields", json_body=to_patch)
            if not patched.get("ok"):
                return {
                    "ok": False,
                    "status_code": patched.get("status_code"),
                    "response": patched.get("response"),
                    "created": created.get("requested") or [],
                    "patch_failed": patched_codes,
                }

        return {
            "ok": True,
            "created": created.get("requested") or [],
            "patched": patched_codes,
            "skipped_locked": skipped_locked,
            "existing": sorted(by_code),
        }

    def sync_case(
        self,
        *,
        case_id: str,
        b2c_status: str,
        pipeline_status: str,
        full_name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        channel: str | None = None,
        source: str | None = None,
        consent: bool | None = True,
        crm_external_id: str | None = None,
        case_url: str | None = None,
        max_reply_hint: str | None = None,
        max_user_id: str | None = None,
        task: str | None = None,
        first_source: str | None = None,
        last_source: str | None = None,
        utm_medium: str | None = None,
        utm_campaign: str | None = None,
        utm_content: str | None = None,
        utm_term: str | None = None,
        landing_variant: str | None = None,
        audience_segment: str | None = None,
        region_bucket: str | None = None,
        referral_code: str | None = None,
        problem_type: str | None = None,
        loss_reason: str | None = None,
    ) -> dict[str, Any]:
        """Создать или обновить сделку. Возвращает lead_id при успехе."""
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "no AMO_SUBDOMAIN/AMO_ACCESS_TOKEN"}

        custom_fields = build_lead_custom_fields(
            case_id=case_id,
            case_url=case_url,
            max_reply_hint=max_reply_hint,
            max_user_id=max_user_id,
            pipeline_status=pipeline_status or b2c_status,
            channel=channel,
            source=source,
            consent=consent,
            first_source=first_source,
            last_source=last_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            utm_content=utm_content,
            utm_term=utm_term,
            landing_variant=landing_variant,
            audience_segment=audience_segment,
            region_bucket=region_bucket,
            referral_code=referral_code,
            problem_type=problem_type,
            loss_reason=loss_reason,
        )
        name = (full_name or "Клиент SFRFR").strip()[:250]
        lead_name = f"Проверка стажа — {name}"[:250]

        stage_key = suggest_amo_stage_key(
            pipeline_status=pipeline_status,
            b2c_status=b2c_status,
            task=task,
            for_create=not (crm_external_id and str(crm_external_id).isdigit()),
        )

        if crm_external_id and str(crm_external_id).isdigit():
            patch_item: dict[str, Any] = {
                "id": int(crm_external_id),
                "name": lead_name,
                "custom_fields_values": custom_fields,
            }
            target_status_id = self.resolve_stage_status_id(stage_key)
            if target_status_id is not None:
                # Не откатывать колонку назад: сверяем с текущим статусом сделки.
                current = self._request("GET", f"/leads/{int(crm_external_id)}")
                cur_id = None
                if current.get("ok") and isinstance(current.get("response"), dict):
                    cur_id = current["response"].get("status_id")
                cur_key = key_for_status_id(self.list_pipeline_statuses(), cur_id)
                if should_move_forward(cur_key, stage_key):
                    patch_item["status_id"] = target_status_id
            result = self._request("PATCH", "/leads", json_body=[patch_item])
            result["case_id"] = case_id
            result["lead_id"] = str(crm_external_id)
            result["crm_url"] = self.lead_url(crm_external_id)
            result["action"] = "update"
            result["amo_stage_key"] = stage_key
            if stage_key == "diag_paid" and result.get("ok"):
                result["task"] = self.create_lead_task(
                    crm_external_id, TASK_DOCS_AFTER_DIAG, complete_till_hours=48
                )
            if stage_key == "review_asked" and result.get("ok"):
                result["task"] = self.create_lead_task(
                    crm_external_id, TASK_REVIEW_REMINDER, complete_till_hours=72
                )
            return result

        contact: dict[str, Any] = {"name": name}
        contact_cf: list[dict[str, Any]] = []
        if phone:
            contact_cf.append(
                {
                    "field_code": "PHONE",
                    "values": [{"value": phone, "enum_code": "MOB"}],
                }
            )
        if email:
            contact_cf.append(
                {
                    "field_code": "EMAIL",
                    "values": [{"value": email, "enum_code": "WORK"}],
                }
            )
        if contact_cf:
            contact["custom_fields_values"] = contact_cf

        lead: dict[str, Any] = {
            "name": lead_name,
            "custom_fields_values": custom_fields,
            "_embedded": {"contacts": [contact]},
        }
        if self.pipeline_id is not None:
            lead["pipeline_id"] = self.pipeline_id
        if self.status_id is not None:
            lead["status_id"] = self.status_id

        result = self._request("POST", "/leads/complex", json_body=[lead])
        result["case_id"] = case_id
        result["action"] = "create"
        result["amo_stage_key"] = "new_lead"
        lead_id = _extract_lead_id(result.get("response"))
        if lead_id:
            result["lead_id"] = lead_id
            result["crm_url"] = self.lead_url(lead_id)
            result["ok"] = True
            result["task"] = self.create_lead_task(
                lead_id, TASK_FIRST_CONTACT, complete_till_hours=24
            )
        return result

    def add_lead_note(self, lead_id: str | int, text: str) -> dict[str, Any]:
        """Обычная текстовая заметка к сделке (не фискальный чек)."""
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "no AMO credentials"}
        body = (text or "").strip()
        if not body:
            return {"ok": False, "skipped": True, "reason": "empty note"}
        payload = [
            {
                "entity_id": int(lead_id),
                "note_type": "common",
                "params": {"text": body[:10000]},
            }
        ]
        result = self._request("POST", "/leads/notes", json_body=payload)
        result["lead_id"] = str(lead_id)
        result["action"] = "note"
        return result


def _extract_lead_id(body: Any) -> str | None:
    if isinstance(body, list) and body:
        first = body[0]
        if isinstance(first, dict) and first.get("id") is not None:
            return str(first["id"])
    if not isinstance(body, dict):
        return None
    embedded = body.get("_embedded") or {}
    leads = embedded.get("leads") or []
    if leads and isinstance(leads[0], dict) and leads[0].get("id") is not None:
        return str(leads[0]["id"])
    if body.get("id") is not None:
        return str(body["id"])
    return None


def sync_case_to_amocrm(
    *,
    case_id: str,
    b2c_status: str,
    pipeline_status: str,
    full_name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    channel: str | None = None,
    source: str | None = None,
    consent: bool | None = True,
    crm_external_id: str | None = None,
    case_url: str | None = None,
    max_reply_hint: str | None = None,
    max_user_id: str | None = None,
    task: str | None = None,
    first_source: str | None = None,
    last_source: str | None = None,
    utm_medium: str | None = None,
    utm_campaign: str | None = None,
    utm_content: str | None = None,
    utm_term: str | None = None,
    landing_variant: str | None = None,
    audience_segment: str | None = None,
    region_bucket: str | None = None,
    referral_code: str | None = None,
    problem_type: str | None = None,
    loss_reason: str | None = None,
) -> dict[str, Any]:
    return AmoCrmClient().sync_case(
        case_id=case_id,
        b2c_status=b2c_status,
        pipeline_status=pipeline_status,
        full_name=full_name,
        phone=phone,
        email=email,
        channel=channel,
        source=source,
        consent=consent,
        crm_external_id=crm_external_id,
        case_url=case_url,
        max_reply_hint=max_reply_hint,
        max_user_id=max_user_id,
        task=task,
        first_source=first_source,
        last_source=last_source,
        utm_medium=utm_medium,
        utm_campaign=utm_campaign,
        utm_content=utm_content,
        utm_term=utm_term,
        landing_variant=landing_variant,
        audience_segment=audience_segment,
        region_bucket=region_bucket,
        referral_code=referral_code,
        problem_type=problem_type,
        loss_reason=loss_reason,
    )


def ensure_amocrm_lead_fields() -> dict[str, Any]:
    return AmoCrmClient().ensure_lead_fields()
