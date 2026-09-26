"""Временный REST-хелпер Yandex Cloud (удалить после задачи). Секреты маскируются."""

import json
import sys
import time
from pathlib import Path

import jwt
import requests

KEY = Path(__file__).resolve().parent.parent / "secrets" / "yc-sa-db01.json"
_TOKEN_CACHE = KEY.parent / ".yc_iam_token.tmp"
SECRET_FIELDS = {"secret", "privateKey", "private_key", "iamToken"}


def token() -> str:
    if _TOKEN_CACHE.exists() and time.time() - _TOKEN_CACHE.stat().st_mtime < 3000:
        return _TOKEN_CACHE.read_text().strip()
    k = json.loads(KEY.read_text(encoding="utf-8"))
    now = int(time.time())
    enc = jwt.encode(
        {
            "aud": "https://iam.api.cloud.yandex.net/iam/v1/tokens",
            "iss": k["service_account_id"],
            "iat": now,
            "exp": now + 3600,
        },
        k["private_key"],
        algorithm="PS256",
        headers={"kid": k["id"]},
    )
    r = requests.post(
        "https://iam.api.cloud.yandex.net/iam/v1/tokens", json={"jwt": enc}, timeout=30
    )
    r.raise_for_status()
    t = r.json()["iamToken"]
    _TOKEN_CACHE.write_text(t)
    return t


def mask(o):
    if isinstance(o, dict):
        return {k: ("***" if k in SECRET_FIELDS else mask(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [mask(x) for x in o]
    return o


def call(method: str, url: str, body=None, params=None):
    r = requests.request(
        method,
        url,
        json=body,
        params=params,
        timeout=60,
        headers={"Authorization": f"Bearer {token()}"},
    )
    try:
        data = r.json()
    except ValueError:
        data = {"_text": r.text[:2000]}
    return r.status_code, data


if __name__ == "__main__":
    m, u = sys.argv[1], sys.argv[2]
    b = (
        json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
        if len(sys.argv) > 3 and sys.argv[3] != "-"
        else None
    )
    p = dict(a.split("=", 1) for a in sys.argv[4:]) or None
    code, data = call(m, u, b, p)
    print(code)
    print(json.dumps(mask(data), ensure_ascii=False, indent=1))
