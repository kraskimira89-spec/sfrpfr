"""One-off: создать SmartCaptcha в YC и сохранить ключи (не коммитить response)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def last_nonempty(*names: str) -> str:
    last = ""
    for line in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        if k.strip() in names:
            vv = v.strip().strip('"').strip("'")
            if vv:
                last = vv
    return last


key = last_nonempty("YANDEX_API_KEY", "YC_API_KEY", "LLM_API_KEY")
folder = last_nonempty("YANDEX_FOLDER_ID", "YC_FOLDER_ID", "LLM_FOLDER_ID")
print("key_len", len(key), "folder", (folder[:8] + "...") if folder else "EMPTY")
if not key or not folder:
    raise SystemExit(2)

list_req = urllib.request.Request(
    f"https://smartcaptcha.api.cloud.yandex.net/smartcaptcha/v1/captchas?folderId={folder}",
    headers={"Authorization": f"Api-Key {key}"},
    method="GET",
)
try:
    with urllib.request.urlopen(list_req, timeout=30) as resp:
        listed = json.loads(resp.read().decode())
        caps = listed.get("captchas") or []
        print("count", len(caps))
        for c in caps[:5]:
            print("existing", c.get("id"), c.get("name"), str(c.get("clientKey") or "")[:12])
except Exception as exc:  # noqa: BLE001
    print("list_err", type(exc).__name__, exc)

body = json.dumps(
    {
        "folderId": folder,
        "name": "sfrfr-proverkastaza",
        "allowedSites": ["proverkastaza.ru", "www.proverkastaza.ru"],
        "complexity": "MEDIUM",
        "preCheckType": "CHECKBOX",
        "challengeType": "IMAGE_TEXT",
    }
).encode()
req = urllib.request.Request(
    "https://smartcaptcha.api.cloud.yandex.net/smartcaptcha/v1/captchas",
    data=body,
    headers={
        "Authorization": f"Api-Key {key}",
        "Content-Type": "application/json",
    },
    method="POST",
)
out = ROOT / "secrets" / "smartcaptcha-create-response.json"
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("created", resp.status, "saved", out.name)
        captcha = data.get("response") or data.get("captcha") or data
        if isinstance(captcha, dict):
            print("id", captcha.get("id"))
            print("client_prefix", str(captcha.get("clientKey") or "")[:10])
            print("server_prefix", str(captcha.get("serverKey") or "")[:10])
except urllib.error.HTTPError as exc:
    err = exc.read().decode(errors="replace")[:1000]
    print("create_http", exc.code, err)
except Exception as exc:  # noqa: BLE001
    print("create_err", type(exc).__name__, exc)
