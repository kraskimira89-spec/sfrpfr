"""API-smoke staff document check (реальный HTTP-контур admin portal).

Не подменяет результат готовым JSON: enqueue → (опционально sync process) → GET detail.

Требует:
  PRECHECK_E2E_API_BASE   например http://127.0.0.1:8000
  PRECHECK_E2E_STAFF_TOKEN  bearer сотрудника
  PRECHECK_E2E_CASE_ID      синтетическое дело

Не трогает production без явных env. Merge/deploy/live MAX — вне скрипта.

Пример:
  .\\.venv\\Scripts\\python.exe tools\\precheck_e2e\\staff_document_check_api_smoke.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _req(
    method: str,
    url: str,
    *,
    token: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any] | list[Any] | str]:
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            code = int(resp.status)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        code = int(exc.code)
    try:
        parsed: dict[str, Any] | list[Any] | str = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        parsed = raw[:500]
    return code, parsed


def main() -> int:
    base = _env("PRECHECK_E2E_API_BASE").rstrip("/")
    token = _env("PRECHECK_E2E_STAFF_TOKEN")
    case_id = _env("PRECHECK_E2E_CASE_ID")
    poll_sec = float(_env("PRECHECK_E2E_POLL_SEC") or "2")
    max_wait = float(_env("PRECHECK_E2E_MAX_WAIT_SEC") or "90")

    print("precheck_e2e staff_document_check_api_smoke", flush=True)
    if not base or not token or not case_id:
        print(
            "RESULT: skip — задайте PRECHECK_E2E_API_BASE, "
            "PRECHECK_E2E_STAFF_TOKEN, PRECHECK_E2E_CASE_ID",
            flush=True,
        )
        return 2

    # 1) карточка до запуска
    code, before = _req("GET", f"{base}/api/portal/admin/cases/{case_id}", token=token)
    print(f"GET case before HTTP {code}", flush=True)
    if code == 403:
        print("RESULT: forbidden — нет прав (ожидаемый негативный контур)", flush=True)
        return 0
    if code != 200 or not isinstance(before, dict):
        print(f"RESULT: fail_before {code}", flush=True)
        return 3

    # 2) реальный enqueue через тот же endpoint, что кнопка «Проверить документы»
    code, queued = _req(
        "POST",
        f"{base}/api/portal/admin/cases/{case_id}/request-review",
        token=token,
        body={},
    )
    print(f"POST request-review HTTP {code}", flush=True)
    if code != 200 or not isinstance(queued, dict):
        print(f"RESULT: fail_enqueue {code} {queued!r}"[:400], flush=True)
        return 4
    doc = queued.get("document_check") if isinstance(queued.get("document_check"), dict) else {}
    job_id = str(doc.get("job_id") or "")
    print(
        f"enqueued job_id={job_id[:8]}… deduped={doc.get('deduped')} status={doc.get('status')}",
        flush=True,
    )
    if not job_id:
        print("RESULT: fail_no_job_id", flush=True)
        return 5

    # 3) poll detail — ждём сохранённый результат (не подставляем)
    deadline = time.time() + max_wait
    last_status = ""
    detail: dict[str, Any] = {}
    while time.time() < deadline:
        code, detail_raw = _req(
            "GET", f"{base}/api/portal/admin/cases/{case_id}", token=token
        )
        if code != 200 or not isinstance(detail_raw, dict):
            print(f"poll fail HTTP {code}", flush=True)
            time.sleep(poll_sec)
            continue
        detail = detail_raw
        check = detail.get("document_check")
        check_d = check if isinstance(check, dict) else {}
        last_status = str(check_d.get("status") or "")
        print(
            f"poll status={last_status} stage={check_d.get('current_stage')}",
            flush=True,
        )
        if last_status in {"completed", "needs_action", "failed"}:
            break
        time.sleep(poll_sec)

    check = detail.get("document_check") if isinstance(detail, dict) else None
    check_d = check if isinstance(check, dict) else {}
    result = check_d.get("result") if isinstance(check_d.get("result"), dict) else {}
    primary = result.get("primary_precheck") if isinstance(result, dict) else None
    print(
        json.dumps(
            {
                "final_status": last_status,
                "has_primary": isinstance(primary, dict),
                "outcome": (primary or {}).get("outcome") if isinstance(primary, dict) else None,
                "findings": len((primary or {}).get("findings") or [])
                if isinstance(primary, dict)
                else 0,
                "stale": check_d.get("stale"),
                "client_notify": (check_d.get("client_notify") or {}).get("status")
                if isinstance(check_d.get("client_notify"), dict)
                else None,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    if last_status not in {"completed", "needs_action", "failed"}:
        print("RESULT: timeout_waiting_job", flush=True)
        return 6
    print("RESULT: ok", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
