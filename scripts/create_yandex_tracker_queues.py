#!/usr/bin/env python3
"""Создать очереди PUB и FUNNEL в Яндекс Трекере (клон конфига SFRFR)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "secrets" / "yandex-tracker.env"
API = "https://api.tracker.yandex.net/v3"

QUEUES = [
    {
        "key": "PUB",
        "name": "Публикации",
        "description": "Контент: MAX, VK, blog, SEO, Директ. Канон: docs/TRACKER/playbook-publish-queue.md",
    },
    {
        "key": "FUNNEL",
        "name": "Воронка клиентов",
        "description": "Ops по этапам воронки без ПДн; CRM — amo. Канон: docs/TRACKER/playbook-funnel-ops.md",
    },
]

ISSUE_TYPES_CONFIG = [
    {
        "issueType": "milestone",
        "workflow": "quickStartV2PresetWorkflow",
        "resolutions": ["fixed"],
    },
    {
        "issueType": "task",
        "workflow": "quickStartV2PresetWorkflow",
        "resolutions": ["fixed", "wontFix", "duplicate"],
    },
]


def load_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise SystemExit(f"Нет файла {path} — заполните secrets/yandex-tracker.env")
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def api_request(method: str, url: str, headers: dict[str, str], body: dict | None = None) -> dict:
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = Request(url, data=data, method=method, headers=headers)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} {method} {url}\n{detail}") from exc


def build_headers(env: dict[str, str]) -> dict[str, str]:
    token = env.get("TRACKER_TOKEN", "")
    if not token:
        raise SystemExit("TRACKER_TOKEN не задан в secrets/yandex-tracker.env")
    headers = {"Authorization": f"OAuth {token}"}
    if org := env.get("TRACKER_CLOUD_ORG_ID"):
        headers["X-Cloud-Org-ID"] = org
    elif org := env.get("TRACKER_ORG_ID"):
        headers["X-Org-ID"] = org
    else:
        raise SystemExit("Нужен TRACKER_ORG_ID или TRACKER_CLOUD_ORG_ID")
    return headers


def get_queue(headers: dict[str, str], key: str) -> dict | None:
    try:
        return api_request("GET", f"{API}/queues/{key}?expand=issueTypesConfig", headers)
    except SystemExit as exc:
        if "404" in str(exc):
            return None
        raise


def create_queue(headers: dict[str, str], spec: dict[str, str], lead: str) -> dict:
    body = {
        "key": spec["key"],
        "name": spec["name"],
        "description": spec["description"],
        "lead": lead,
        "defaultType": "task",
        "defaultPriority": "normal",
        "issueTypesConfig": ISSUE_TYPES_CONFIG,
    }
    return api_request("POST", f"{API}/queues/", headers, body)


def move_issue(headers: dict[str, str], issue_key: str, queue: str) -> dict:
    return api_request(
        "POST",
        f"{API}/issues/{issue_key}/_move?queue={queue}&notify=false&notifyAuthor=false&initialStatus=true",
        headers,
        {},
    )


def main() -> int:
    env = load_env(ENV_PATH)
    headers = build_headers(env)

    sfrfr = get_queue(headers, "SFRFR")
    if not sfrfr:
        raise SystemExit("Очередь SFRFR не найдена — сначала создайте SFRFR")
    lead = sfrfr.get("lead", {}).get("id") or sfrfr.get("lead", {}).get("cloudUid")
    if not lead:
        raise SystemExit("Не удалось определить lead из SFRFR")

    created: list[str] = []
    existing: list[str] = []

    for spec in QUEUES:
        key = spec["key"]
        if get_queue(headers, key):
            existing.append(key)
            print(f"OK  очередь {key} уже есть")
            continue
        result = create_queue(headers, spec, str(lead))
        created.append(key)
        print(f"OK  создана очередь {key}: {result.get('self', key)}")

    print(json.dumps({"created": created, "existing": existing}, ensure_ascii=False))

    moves = [
        ("SFRFR-6", "PUB"),
        ("SFRFR-8", "PUB"),
        ("SFRFR-9", "PUB"),
        ("SFRFR-10", "PUB"),
        ("SFRFR-7", "FUNNEL"),
        ("SFRFR-11", "FUNNEL"),
        ("SFRFR-12", "FUNNEL"),
    ]
    moved: list[str] = []
    skipped: list[str] = []
    for issue_key, queue in moves:
        try:
            result = move_issue(headers, issue_key, queue)
            new_key = result.get("key", issue_key)
            moved.append(f"{issue_key}->{new_key}")
            print(f"OK  move {issue_key} -> {new_key}")
        except SystemExit as exc:
            msg = str(exc)
            if "404" in msg:
                skipped.append(f"{issue_key}:not_found")
                print(f"SKIP {issue_key} not found")
            elif "422" in msg or "PUB-" in msg or "FUNNEL-" in msg:
                skipped.append(f"{issue_key}:already_moved")
                print(f"SKIP {issue_key} already in target queue")
            else:
                raise

    print(json.dumps({"moved": moved, "skipped": skipped}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
