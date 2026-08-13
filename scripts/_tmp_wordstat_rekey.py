#!/usr/bin/env python3
"""Перевыпуск Wordstat Api-Key для SA из yc-cloud.env. Не коммитить."""
from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip("\"'")
    return out


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def main() -> None:
    yc = load_env(ROOT / "secrets/yc-cloud.env")
    key_path = yc["YC_SERVICE_ACCOUNT_KEY_FILE"]
    if not Path(key_path).is_absolute():
        key_path = str(ROOT / key_path)
    sa_key = json.loads(Path(key_path).read_text(encoding="utf-8"))
    folder_id = yc["YC_FOLDER_ID"]
    sa_id = sa_key["service_account_id"]

    now = int(time.time())
    header = {"alg": "PS256", "typ": "JWT", "kid": sa_key["id"]}
    payload = {
        "aud": "https://iam.api.cloud.yandex.net/iam/v1/tokens",
        "iss": sa_id,
        "iat": now,
        "exp": now + 3600,
    }
    signing_input = (
        f"{b64url(json.dumps(header, separators=(',', ':')).encode())}."
        f"{b64url(json.dumps(payload, separators=(',', ':')).encode())}"
    ).encode()
    private_key = serialization.load_pem_private_key(
        sa_key["private_key"].encode(), password=None
    )
    signature = private_key.sign(
        signing_input,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    jwt = signing_input.decode() + "." + b64url(signature)
    req = urllib.request.Request(
        "https://iam.api.cloud.yandex.net/iam/v1/tokens",
        data=json.dumps({"jwt": jwt}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        iam = json.loads(resp.read().decode())["iamToken"]

    def iam_req(method: str, url: str, body: dict | None = None):
        data = None if body is None else json.dumps(body).encode()
        r = urllib.request.Request(
            url,
            data=data,
            headers={"Authorization": f"Bearer {iam}", "Content-Type": "application/json"},
            method=method,
        )
        try:
            with urllib.request.urlopen(r, timeout=60) as resp:
                raw = resp.read().decode()
                return resp.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="replace")
            try:
                return e.code, json.loads(raw or "{}")
            except json.JSONDecodeError:
                return e.code, {"raw": raw}

    code, out = iam_req(
        "POST",
        "https://iam.api.cloud.yandex.net/iam/v1/apiKeys",
        {
            "serviceAccountId": sa_id,
            "description": "SFRFR Wordstat SEO proverkastaza (auto)",
            "scopes": ["yc.search-api.execute"],
        },
    )
    if code not in (200, 201) or "secret" not in out:
        raise SystemExit(f"create key failed: {code} {out}")
    secret = out["secret"]
    key_id = (out.get("apiKey") or {}).get("id", "")
    (ROOT / "secrets/yandex-wordstat.env").write_text(
        "# Wordstat Search API — НЕ коммитить\n"
        f"YANDEX_WORDSTAT_API_KEY={secret}\n"
        f"YANDEX_WORDSTAT_FOLDER_ID={folder_id}\n"
        f"# key_id={key_id} SA={sa_id}\n",
        encoding="utf-8",
    )
    body = json.dumps(
        {
            "phrase": "архивная справка о стаже",
            "numPhrases": 5,
            "folderId": folder_id,
            "regions": ["225"],
        },
        ensure_ascii=False,
    ).encode()
    req = urllib.request.Request(
        "https://searchapi.api.cloud.yandex.net/v2/wordstat/topRequests",
        data=body,
        headers={"Authorization": f"Api-Key {secret}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode())
    print(f"ok key_id={key_id} totalCount={data.get('totalCount')}")


if __name__ == "__main__":
    main()
