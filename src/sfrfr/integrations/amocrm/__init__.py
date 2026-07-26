"""Интеграция amoCRM API v4: контакт + сделка, custom fields, без файлов."""

from __future__ import annotations

from typing import Any

import httpx

from sfrfr.core.config import get_settings
from sfrfr.integrations.amocrm.fields import LEAD_FIELD_SPECS, build_lead_custom_fields


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

    def ensure_lead_fields(self) -> dict[str, Any]:
        """Создать недостающие custom fields сделки по code из ТЗ-12."""
        listed = self.list_lead_custom_fields()
        if listed.get("skipped") or not listed.get("ok"):
            return listed
        existing = {
            str(item.get("code") or "").upper()
            for item in (listed.get("response") or {})
            .get("_embedded", {})
            .get("custom_fields", [])
            if item.get("code")
        }
        to_create = [
            {"name": spec["name"], "type": spec["type"], "code": spec["code"]}
            for spec in LEAD_FIELD_SPECS
            if spec["code"].upper() not in existing
        ]
        if not to_create:
            return {"ok": True, "created": [], "existing": sorted(existing)}
        created = self._request("POST", "/leads/custom_fields", json_body=to_create)
        created["requested"] = [f["code"] for f in to_create]
        return created

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
        task: str | None = None,
    ) -> dict[str, Any]:
        """Создать или обновить сделку. Возвращает lead_id при успехе."""
        if not self.available:
            return {"ok": False, "skipped": True, "reason": "no AMO_SUBDOMAIN/AMO_ACCESS_TOKEN"}

        custom_fields = build_lead_custom_fields(
            case_id=case_id,
            case_url=case_url,
            pipeline_status=pipeline_status or b2c_status,
            channel=channel,
            source=source,
            consent=consent,
        )
        name = (full_name or "Клиент SFRFR").strip()[:250]
        lead_name = f"Проверка стажа — {name}"[:250]
        if task:
            lead_name = f"{lead_name} [{task}]"[:250]

        if crm_external_id and str(crm_external_id).isdigit():
            patch_body: list[dict[str, Any]] = [
                {
                    "id": int(crm_external_id),
                    "name": lead_name,
                    "custom_fields_values": custom_fields,
                }
            ]
            result = self._request("PATCH", "/leads", json_body=patch_body)
            result["case_id"] = case_id
            result["lead_id"] = str(crm_external_id)
            result["crm_url"] = self.lead_url(crm_external_id)
            result["action"] = "update"
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
        lead_id = _extract_lead_id(result.get("response"))
        if lead_id:
            result["lead_id"] = lead_id
            result["crm_url"] = self.lead_url(lead_id)
            result["ok"] = True
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
    task: str | None = None,
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
        task=task,
    )


def ensure_amocrm_lead_fields() -> dict[str, Any]:
    return AmoCrmClient().ensure_lead_fields()
