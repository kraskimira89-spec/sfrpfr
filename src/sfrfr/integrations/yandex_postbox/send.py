"""Отправка писем через Yandex Cloud Postbox (SES-совместимый API)."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from sfrfr.core.config import get_settings
from sfrfr.integrations.yandex_postbox.aws_sigv4 import sigv4_headers

logger = logging.getLogger(__name__)

_DEFAULT_ENDPOINT = "https://postbox.cloud.yandex.net"
_PATH = "/v2/email/outbound-emails"


def postbox_configured() -> bool:
    s = get_settings()
    return bool(
        s.yandex_postbox_enabled
        and (s.yandex_postbox_from_email or "").strip()
        and (s.yandex_postbox_access_key_id or "").strip()
        and (s.yandex_postbox_secret_access_key or "").strip()
    )


def send_email_postbox(
    *,
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
    from_email: str | None = None,
    from_name: str | None = None,
    configuration_set: str | None = None,
    timeout_sec: float = 30.0,
) -> dict[str, Any]:
    """POST /v2/email/outbound-emails. MessageId из ответа → provider_message_id."""
    settings = get_settings()
    key_id = (settings.yandex_postbox_access_key_id or "").strip()
    secret = (settings.yandex_postbox_secret_access_key or "").strip()
    if not key_id or not secret:
        return {"ok": False, "error": "postbox_credentials_missing"}

    to_addr = (to or "").strip()
    if "@" not in to_addr:
        return {"ok": False, "error": "invalid_to"}

    source = (from_email or settings.yandex_postbox_from_email or "").strip()
    if not source or "@" not in source:
        return {"ok": False, "error": "postbox_from_missing"}

    display = (from_name or "").strip()
    from_header = f"{display} <{source}>" if display else source

    body_obj: dict[str, Any] = {
        "Text": {"Data": text, "Charset": "UTF-8"},
    }
    if (html or "").strip():
        body_obj["Html"] = {"Data": html.strip(), "Charset": "UTF-8"}

    payload: dict[str, Any] = {
        "FromEmailAddress": from_header,
        "Destination": {"ToAddresses": [to_addr]},
        "Content": {
            "Simple": {
                "Subject": {"Data": subject[:200], "Charset": "UTF-8"},
                "Body": body_obj,
            }
        },
    }
    cfg = (configuration_set or settings.yandex_postbox_configuration_set or "").strip()
    if cfg:
        payload["ConfigurationSetName"] = cfg

    endpoint = (settings.yandex_postbox_endpoint or _DEFAULT_ENDPOINT).rstrip("/")
    parsed = urlparse(endpoint)
    host = parsed.netloc or "postbox.cloud.yandex.net"
    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = sigv4_headers(
        method="POST",
        url_path=_PATH,
        host=host,
        body=body_bytes,
        access_key_id=key_id,
        secret_access_key=secret,
    )
    url = f"{endpoint}{_PATH}"
    try:
        with httpx.Client(timeout=timeout_sec) as client:
            resp = client.post(url, content=body_bytes, headers=headers)
    except Exception as exc:  # noqa: BLE001
        logger.exception("postbox send failed")
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}

    if resp.status_code >= 400:
        detail = (resp.text or "")[:300]
        return {
            "ok": False,
            "error": "postbox_http_error",
            "status_code": resp.status_code,
            "detail": detail,
        }

    try:
        data = resp.json()
    except Exception:  # noqa: BLE001
        data = {}
    message_id = str(data.get("MessageId") or data.get("messageId") or "").strip()
    if not message_id:
        return {
            "ok": False,
            "error": "postbox_no_message_id",
            "detail": (resp.text or "")[:200],
        }
    return {
        "ok": True,
        "to": to_addr,
        "from": from_header,
        "subject": subject[:200],
        "message_id": message_id,
        "provider": "yandex_postbox",
    }
