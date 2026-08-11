"""Создать этапы воронки amo под playbook funnel + LOSS_REASON required на отказе.

Запуск на VPS:
  cd /opt/sfrfr && . .venv/bin/activate && set -a && . ./.env && set +a
  python scripts/amocrm_ensure_pipeline_stages.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sfrfr.integrations.amocrm.pipeline_stages import AMO_STAGES_TO_ENSURE  # noqa: E402

# Палитра цветов статусов amo (невалидный hex даёт 400).
AMO_STATUS_COLORS = (
    "#fffeb2",
    "#99ccff",
    "#ffff99",
    "#ffcc66",
    "#ffcccc",
    "#ffce5a",
    "#ff8f92",
    "#d6eaff",
    "#c1c1c1",
    "#CCFF66",
)


def load_dotenv(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v.strip().strip('"').strip("'")
    return env


def req(base: str, token: str, method: str, path: str, body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw[:500]}
        return e.code, parsed


def main() -> int:
    env = {**load_dotenv(ROOT / "secrets" / "amocrm.env"), **load_dotenv(ROOT / ".env")}
    for k, v in env.items():
        os.environ.setdefault(k, v)

    sub = os.environ.get("AMO_SUBDOMAIN", "").strip()
    token = os.environ.get("AMO_ACCESS_TOKEN", "").strip()
    pipe_id = os.environ.get("AMO_PIPELINE_ID", "").strip()
    if not (sub and token and pipe_id):
        print("NEED AMO_SUBDOMAIN, AMO_ACCESS_TOKEN, AMO_PIPELINE_ID")
        return 1

    base = f"https://{sub}.amocrm.ru/api/v4"
    code, pipe = req(base, token, "GET", f"/leads/pipelines/{pipe_id}")
    if code != 200:
        print("pipeline_get_failed", code, pipe)
        return 1

    statuses = (pipe.get("_embedded") or {}).get("statuses") or []
    by_name = {str(s.get("name") or "").strip().casefold(): s for s in statuses}
    created: list[str] = []
    renamed: list[str] = []

    # Переименовать устаревшие редактируемые этапы под канон (по порядку sort).
    editable = [
        s
        for s in statuses
        if s.get("is_editable")
        and str(s.get("name") or "") not in AMO_STAGES_TO_ENSURE
        and str(s.get("name") or "") != "Новый лид"
    ]
    editable.sort(key=lambda x: int(x.get("sort") or 0))
    need_names = [n for n in AMO_STAGES_TO_ENSURE if n.casefold() not in by_name]
    # «Закрыто успешно» → системный «Успешно реализовано»
    need_names = [n for n in need_names if n != "Закрыто успешно"]

    for stage, new_name in zip(editable, need_names):
        c, body = req(
            base,
            token,
            "PATCH",
            f"/leads/pipelines/{pipe_id}/statuses/{stage['id']}",
            {"name": new_name},
        )
        print("rename", stage.get("name"), "->", new_name, "HTTP", c)
        if c < 400:
            renamed.append(f"{stage.get('name')}->{new_name}")
            by_name[new_name.casefold()] = {**stage, "name": new_name}
            by_name.pop(str(stage.get("name") or "").casefold(), None)

    need_names = [n for n in AMO_STAGES_TO_ENSURE if n.casefold() not in by_name and n != "Закрыто успешно"]
    # Только цвета, уже используемые в этой воронке (иначе API 400 NotSupportedChoice).
    known_colors = [
        str(s.get("color") or "")
        for s in statuses
        if s.get("color") and s.get("is_editable")
    ] or list(AMO_STATUS_COLORS)
    sort_base = 70
    for i, name in enumerate(need_names):
        color = known_colors[i % len(known_colors)]
        payload = [{"name": name, "sort": sort_base + i * 10, "color": color}]
        c, body = req(base, token, "POST", f"/leads/pipelines/{pipe_id}/statuses", payload)
        print("create", name, "HTTP", c, color)
        if c >= 400:
            # fallback: без цвета
            payload2 = [{"name": name, "sort": sort_base + i * 10}]
            c, body = req(base, token, "POST", f"/leads/pipelines/{pipe_id}/statuses", payload2)
            print("create_retry_no_color", name, "HTTP", c)
            if c >= 400:
                print(body)
                continue
        created.append(name)
        emb = (body.get("_embedded") or {}).get("statuses") or []
        if emb:
            by_name[name.casefold()] = emb[0]

    # Выстроить sort по канону: Новый лид → … → Отзыв получен
    code, pipe = req(base, token, "GET", f"/leads/pipelines/{pipe_id}")
    statuses = (pipe.get("_embedded") or {}).get("statuses") or []
    by_name = {str(s.get("name") or "").strip(): s for s in statuses}
    sort_val = 20
    order_names = ["Новый лид"] + [
        n for n in AMO_STAGES_TO_ENSURE if n not in {"Новый лид", "Закрыто успешно"}
    ]
    for name in order_names:
        s = by_name.get(name)
        if not s or not s.get("is_editable"):
            continue
        c, _ = req(
            base,
            token,
            "PATCH",
            f"/leads/pipelines/{pipe_id}/statuses/{s['id']}",
            {"name": name, "sort": sort_val},
        )
        print("sort", name, sort_val, "HTTP", c)
        sort_val += 10

    # refresh
    code, pipe = req(base, token, "GET", f"/leads/pipelines/{pipe_id}")
    statuses = (pipe.get("_embedded") or {}).get("statuses") or []
    print("=== statuses ===")
    for s in sorted(statuses, key=lambda x: int(x.get("sort") or 0)):
        print(f"{s.get('id')}\t{s.get('name')}\tsort={s.get('sort')}\ttype={s.get('type')}")

    # Системный отказ: обычно «Закрыто и не реализовано»
    lost = next(
        (
            s
            for s in statuses
            if "не реализовано" in str(s.get("name") or "").casefold()
        ),
        None,
    )

    # LOSS_REASON обязателен при уходе в отказ
    code, fields = req(base, token, "GET", "/leads/custom_fields?limit=250")
    if code == 200:
        rows = (fields.get("_embedded") or {}).get("custom_fields") or []
        loss = next((f for f in rows if str(f.get("code") or "") == "LOSS_REASON"), None)
        if loss and lost and lost.get("id"):
            pipe_id_int = int(pipe_id)
            lost_id = int(lost["id"])
            required = [{"status_id": lost_id, "pipeline_id": pipe_id_int}]
            c, body = req(
                base,
                token,
                "PATCH",
                f"/leads/custom_fields/{loss['id']}",
                {"required_statuses": required},
            )
            print("LOSS_REASON required_statuses HTTP", c, "lost_id", lost_id)
            if c >= 400:
                print(body)
        elif not loss:
            print("LOSS_REASON field missing — run sfrfr amocrm-ensure-fields")
        else:
            print("lost status not found — set LOSS_REASON required manually in UI")

    print("renamed", renamed)
    print("created", created)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
