#!/usr/bin/env python3
"""Добавить proverkastaza.ru в Яндекс Вебмастер и запустить META_TAG verification.

Env (secrets/yandex-webmaster.env):
  YANDEX_WEBMASTER_OAUTH_ACCESS_TOKEN
  YANDEX_WEBMASTER_SITE_URL=https://proverkastaza.ru
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.webmaster.yandex.net/v4"


def load_dotenv() -> None:
    root = Path(__file__).resolve().parents[1]
    for rel in ("secrets/yandex-webmaster.env", ".env"):
        path = root / rel
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip("\"'")
            if k and k not in os.environ:
                os.environ[k] = v


def api(method: str, path: str, body: dict | None = None) -> tuple[int, dict | list | None]:
    token = os.environ.get("YANDEX_WEBMASTER_OAUTH_ACCESS_TOKEN", "").strip()
    if not token or not token.startswith("y0"):
        raise SystemExit("Нужен YANDEX_WEBMASTER_OAUTH_ACCESS_TOKEN вида y0_…")
    url = f"{API}{path}"
    data = None
    headers = {
        "Authorization": f"OAuth {token}",
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw) if raw else None
            return resp.status, parsed
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(err)
        except json.JSONDecodeError:
            parsed = {"raw": err}
        return e.code, parsed


def site_url() -> str:
    raw = os.environ.get("YANDEX_WEBMASTER_SITE_URL", "https://proverkastaza.ru").strip()
    if "://" not in raw:
        raw = f"https://{raw}"
    return raw.rstrip("/")


def main() -> int:
    load_dotenv()
    url = site_url()
    print(f"site={url}")

    code, user = api("GET", "/user")
    if code != 200 or not isinstance(user, dict):
        raise SystemExit(f"GET /user failed: {code} {user}")
    uid = user.get("user_id") or user.get("id")
    print(f"user_id={uid}")

    code, hosts = api("GET", f"/user/{uid}/hosts")
    if code != 200 or not isinstance(hosts, dict):
        raise SystemExit(f"GET hosts failed: {code} {hosts}")

    # Предпочитаем HTTPS без www; иначе точное совпадение site URL.
    preferred = None
    candidates: list[tuple[str, bool, str]] = []
    for h in hosts.get("hosts") or []:
        hu = (h.get("ascii_host_url") or h.get("host_url") or "").rstrip("/")
        hid = str(h.get("host_id") or "")
        is_ver = bool(h.get("verified"))
        print(f"  known: {hu} id={hid} verified={is_ver}")
        if "proverkastaza.ru" not in hu and url not in hu and hu not in url:
            continue
        candidates.append((hid, is_ver, hu))
        if hid == "https:proverkastaza.ru:443":
            preferred = (hid, is_ver)

    host_id: str | None = None
    verified = False
    if preferred:
        host_id, verified = preferred
    elif candidates:
        # точное совпадение URL, иначе первый
        for hid, is_ver, hu in candidates:
            if url.rstrip("/") == hu.rstrip("/"):
                host_id, verified = hid, is_ver
                break
        if not host_id:
            host_id, verified, _ = candidates[0]

    if not host_id:
        print("adding host…")
        code, added = api("POST", f"/user/{uid}/hosts", {"host_url": url})
        if code in (200, 201) and isinstance(added, dict):
            host_id = added.get("host_id")
            print(f"added host_id={host_id}")
        elif code == 409 and isinstance(added, dict):
            host_id = added.get("host_id")
            verified = bool(added.get("verified"))
            print(f"already added host_id={host_id} verified={verified}")
        else:
            raise SystemExit(f"POST host failed: {code} {added}")

    assert host_id
    host_id_enc = urllib.parse.quote(str(host_id), safe="")

    code, ver = api("GET", f"/user/{uid}/hosts/{host_id_enc}/verification")
    print(f"verification GET {code}: {json.dumps(ver, ensure_ascii=False)}")
    uin = None
    state = None
    if isinstance(ver, dict):
        uin = ver.get("verification_uin") or ver.get("uin")
        state = ver.get("verification_state") or ver.get("state")

    if state == "VERIFIED" or verified:
        print("OK: already VERIFIED")
        print(f"YANDEX_WEBMASTER_HOST_ID={host_id}")
        return 0

    if uin:
        print(f"verification_uin={uin} — put into meta yandex-verification")
        # Write hint file for deploy (no secrets beyond public uin)
        hint = Path(__file__).resolve().parents[1] / "secrets" / "yandex-webmaster-uin.txt"
        hint.write_text(str(uin) + "\n", encoding="utf-8")

    print("start META_TAG verification…")
    code, started = api(
        "POST",
        f"/user/{uid}/hosts/{host_id_enc}/verification?verification_type=META_TAG",
        {},
    )
    print(f"verification POST {code}: {json.dumps(started, ensure_ascii=False)}")
    if isinstance(started, dict) and started.get("verification_uin"):
        uin = started["verification_uin"]
        hint = Path(__file__).resolve().parents[1] / "secrets" / "yandex-webmaster-uin.txt"
        hint.write_text(str(uin) + "\n", encoding="utf-8")
        print(f"use meta content={uin}")

    print(f"YANDEX_WEBMASTER_HOST_ID={host_id}")
    if uin:
        print(f"YANDEX_WEBMASTER_VERIFICATION_UIN={uin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
