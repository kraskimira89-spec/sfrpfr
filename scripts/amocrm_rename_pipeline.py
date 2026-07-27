"""Переименовать воронку; добавить этап «Новый лид»; обновить secrets/amocrm.env."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "secrets" / "amocrm.env"


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v
    return env


def write_env(path: Path, updates: dict[str, str]) -> None:
    env = load_env(path)
    env.update(updates)
    lines = [
        "# amoCRM — локальная копия (secrets/ в .gitignore, НЕ коммитить)",
        "# Аккаунт: https://proverkastaza.amocrm.ru/",
        "",
        f"AMO_SUBDOMAIN={env.get('AMO_SUBDOMAIN', 'proverkastaza')}",
        f"AMO_ACCESS_TOKEN={env['AMO_ACCESS_TOKEN']}",
        f"AMO_PIPELINE_ID={env['AMO_PIPELINE_ID']}",
        f"AMO_STATUS_ID={env['AMO_STATUS_ID']}",
        f"AMO_CASE_URL_TEMPLATE={env.get('AMO_CASE_URL_TEMPLATE', 'https://{subdomain}.amocrm.ru/leads/detail/{id}')}",
        "",
        "# AMO_INTEGRATION_ID=8fb44480-d514-4df6-bd89-b18dac6c0e75",
        f"# Воронка «Проверка стажа» id={env['AMO_PIPELINE_ID']}, этап «Новый лид» id={env['AMO_STATUS_ID']}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


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
        with urllib.request.urlopen(request, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
        return e.code, parsed


def main() -> None:
    env = load_env(ENV_PATH)
    sub = env["AMO_SUBDOMAIN"]
    token = env["AMO_ACCESS_TOKEN"]
    pipe_id = env["AMO_PIPELINE_ID"]
    base = f"https://{sub}.amocrm.ru/api/v4"

    code, pipe = req(base, token, "GET", f"/leads/pipelines/{pipe_id}")
    assert code == 200, pipe
    if pipe.get("name") != "Проверка стажа":
        code, pipe = req(
            base, token, "PATCH", f"/leads/pipelines/{pipe_id}", {"name": "Проверка стажа"}
        )
        print("pipeline_renamed", code, pipe.get("name") if isinstance(pipe, dict) else pipe)
    else:
        print("pipeline_ok", pipe.get("name"))

    code, pipe = req(base, token, "GET", f"/leads/pipelines/{pipe_id}")
    statuses = (pipe.get("_embedded") or {}).get("statuses") or []
    new_lead = next((s for s in statuses if s.get("name") == "Новый лид"), None)
    if new_lead:
        status_id = str(new_lead["id"])
        print("status_exists", status_id)
    else:
        # Первый этап type=1 (неразобранное) не редактируется — создаём свой.
        code, created = req(
            base,
            token,
            "POST",
            f"/leads/pipelines/{pipe_id}/statuses",
            [{"name": "Новый лид", "sort": 15, "color": "#fffeb2"}],
        )
        print("status_create", code)
        if code >= 400:
            raise SystemExit(created)
        embedded = (created.get("_embedded") or {}).get("statuses") or []
        if not embedded and isinstance(created, list):
            embedded = created
        status_id = str(embedded[0]["id"])
        print("status_created", status_id)

    write_env(ENV_PATH, {"AMO_PIPELINE_ID": str(pipe_id), "AMO_STATUS_ID": status_id})
    print("env_updated", ENV_PATH)

    # Тестовая сделка
    from sfrfr.core.config import get_settings
    from sfrfr.integrations.amocrm import sync_case_to_amocrm

    get_settings.cache_clear()
    # temporarily force from file for this process
    import os

    for k, v in load_env(ENV_PATH).items():
        os.environ[k] = v
    get_settings.cache_clear()

    result = sync_case_to_amocrm(
        case_id="00000000-0000-4000-8000-000000000001",
        b2c_status="lead",
        pipeline_status="intake",
        full_name="Тест SFRFR",
        phone="+79990001122",
        email="test-sfrfr@example.com",
        channel="unset",
        source="amocrm_setup_test",
        consent=True,
        case_url="https://admin.proverkastaza.ru/?case=00000000-0000-4000-8000-000000000001",
        task="setup_test",
    )
    print("test_sync", json.dumps({k: result.get(k) for k in ("ok", "skipped", "lead_id", "crm_url", "status_code", "action", "error")}, ensure_ascii=False))
    if result.get("response") and not result.get("lead_id"):
        print("test_response_snip", str(result.get("response"))[:400])


if __name__ == "__main__":
    main()
