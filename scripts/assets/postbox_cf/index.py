# Cloudflare-style: Postbox event → SFRFR webhook (Python 3.12 CF runtime).
# Env (Lockbox / CF environment):
#   SFRFR_POSTBOX_WEBHOOK_URL=https://api.proverkastaza.ru/api/webhooks/email/postbox
#   SFRFR_POSTBOX_BASIC=<base64(user:pass)>

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request


def _decode_body(raw: object) -> object:
    if isinstance(raw, (dict, list)):
        return raw
    if not isinstance(raw, str) or not raw:
        return {}
    text = raw
    try:
        if not raw.lstrip().startswith(("{", "[")):
            text = base64.b64decode(raw).decode("utf-8")
        return json.loads(text)
    except Exception:  # noqa: BLE001
        return {"raw": raw[:500]}


def handler(event: dict, context: object) -> dict:
    url = (os.environ.get("SFRFR_POSTBOX_WEBHOOK_URL") or "").strip()
    auth = (os.environ.get("SFRFR_POSTBOX_BASIC") or "").strip()
    if not url or not auth:
        raise RuntimeError("SFRFR_POSTBOX_WEBHOOK_URL / SFRFR_POSTBOX_BASIC missing")

    forwarded = 0
    errors: list[str] = []
    for msg in event.get("messages") or [event]:
        details = msg.get("details") if isinstance(msg, dict) else None
        if not isinstance(details, dict):
            details = msg if isinstance(msg, dict) else {}
        message = details.get("message") if isinstance(details.get("message"), dict) else details
        raw = message.get("data") if isinstance(message, dict) else None
        body_obj = _decode_body(raw if raw is not None else details)
        data = json.dumps(body_obj, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Basic {auth}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                _ = resp.read()
            forwarded += 1
        except urllib.error.HTTPError as exc:
            errors.append(f"http_{exc.code}")
        except Exception as exc:  # noqa: BLE001
            errors.append(type(exc).__name__)

    return {"ok": not errors, "forwarded": forwarded, "errors": errors}
