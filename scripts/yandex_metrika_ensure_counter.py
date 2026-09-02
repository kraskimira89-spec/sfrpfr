#!/usr/bin/env python3
"""Счётчик Метрики: цели, filter_robots, exclude IP, cut_parameter.

Env (secrets/yandex-metrika.env):
  YANDEX_METRIKA_OAUTH_ACCESS_TOKEN
  YANDEX_METRIKA_SITE_URL=https://proverkastaza.ru
  YANDEX_METRIKA_COUNTER_NAME=Проверка стажа
  YANDEX_METRIKA_EXCLUDE_IPS=1.2.3.4,5.6.7.8   # опционально
  YANDEX_METRIKA_EXCLUDE_MY_IP=1               # добавить публичный IP запуска (по умолч. 1)
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api-metrika.yandex.net/management/v1"
GOALS = (
    # §7.1
    ("max_click", "Клик Открыть в MAX"),
    ("phone_click", "Клик Позвонить"),
    ("contacts_click", "Клик Контакты"),
    ("lead_start", "Старт заявки / фокус формы"),
    ("lead_ok", "Заявка отправлена (без ПДн)"),
    ("tariffs_view", "Просмотр тарифов"),
    ("tariff_view", "Просмотр тарифов (legacy)"),
    ("form_error", "Ошибка отправки формы"),
    ("cabinet_click", "Клик в кабинет"),
    # §7.2 клиентские
    ("segment_page_view", "Просмотр сегментной страницы"),
    ("max_chat_click", "Клик в личный чат MAX"),
    ("max_channel_click", "Клик в канал MAX"),
    ("callback_click", "Клик Позвонить (сегмент)"),
    ("checklist_download", "Скачивание чек-листа"),
    # §7.2 серверные/CRM (создаём цели заранее; без ПДн в params)
    ("qualification_started", "Квалификация начата"),
    ("qualification_completed", "Квалификация завершена"),
    ("diagnostic_offered", "Предложена диагностика"),
    ("diagnostic_paid", "Оплачена диагностика"),
    ("service_paid", "Оплачена услуга"),
    ("chat_payment_nudge", "Бот предложил оплату в чате"),
    ("chat_payment_nudge_paid", "Оплата после нуджа из чата"),
)
# Параметры URL, которые вырезаем до сохранения хита (ПДн / секреты).
CUT_URL_PARAMS = (
    "email",
    "mail",
    "e-mail",
    "phone",
    "tel",
    "telephone",
    "mobile",
    "fio",
    "name",
    "firstname",
    "lastname",
    "snils",
    "password",
    "pass",
    "token",
    "access_token",
)


def load_dotenv_files() -> None:
    root = Path(__file__).resolve().parents[1]
    for rel in ("secrets/yandex-metrika.env", ".env"):
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


def api(method: str, path: str, body: dict | None = None) -> dict:
    token = os.environ.get("YANDEX_METRIKA_OAUTH_ACCESS_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "Нет YANDEX_METRIKA_OAUTH_ACCESS_TOKEN. См. docs/ops/yandex-metrika-setup.md"
        )
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
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code} {method} {path}\n{err}") from e


def site_host() -> str:
    raw = os.environ.get("YANDEX_METRIKA_SITE_URL", "https://proverkastaza.ru").strip()
    host = urllib.parse.urlparse(raw if "://" in raw else f"https://{raw}").hostname
    if not host:
        raise SystemExit("Некорректный YANDEX_METRIKA_SITE_URL")
    return host.lower()


def find_counter(host: str) -> dict | None:
    data = api("GET", "/counters")
    for c in data.get("counters") or []:
        site = (c.get("site") or "").lower()
        site2 = ((c.get("site2") or {}).get("site") or "").lower()
        if host in (site, site2) or site.endswith(host) or host in site:
            return c
        mirrors = c.get("mirrors2") or c.get("mirrors") or []
        for m in mirrors:
            msite = (m.get("site") if isinstance(m, dict) else str(m) or "").lower()
            if host in msite or msite == host:
                return c
    return None


def create_counter(host: str) -> dict:
    name = os.environ.get("YANDEX_METRIKA_COUNTER_NAME", "Проверка стажа").strip()
    body = {
        "counter": {
            "name": name,
            "site2": {"site": host},
            "filter_robots": 1,
        }
    }
    return api("POST", "/counters", body)


def ensure_counter_settings(counter_id: int) -> None:
    data = api("GET", f"/counter/{counter_id}")
    counter = data.get("counter") or data
    fr = counter.get("filter_robots")
    if fr in (1, "1", True):
        print("  filter_robots=1 (ok)")
        return
    print(f"  enabling filter_robots (was {fr!r})")
    api(
        "PUT",
        f"/counter/{counter_id}",
        {"counter": {"filter_robots": 1}},
    )


def list_goals(counter_id: int) -> list[dict]:
    data = api("GET", f"/counter/{counter_id}/goals")
    return list(data.get("goals") or [])


def ensure_action_goal(counter_id: int, ident: str, title: str, existing: list[dict]) -> None:
    for g in existing:
        conds = g.get("conditions") or []
        for cond in conds:
            if (cond.get("url") or "") == ident:
                print(f"  goal ok: {ident} (id={g.get('id')})")
                return
        # Не матчить только по похожему имени — иначе tariffs_view ≈ tariff_view.
        if (g.get("name") or "") == title and (g.get("type") or "") == "action":
            # имя совпало, но условие другое — создаём отдельную цель
            has_ident = any((c.get("url") or "") == ident for c in conds)
            if has_ident:
                print(f"  goal ok by name: {ident} (id={g.get('id')})")
                return
    body = {
        "goal": {
            "name": title,
            "type": "action",
            "is_retargeting": 0,
            "conditions": [{"type": "exact", "url": ident}],
        }
    }
    out = api("POST", f"/counter/{counter_id}/goals", body)
    gid = (out.get("goal") or {}).get("id")
    print(f"  goal created: {ident} (id={gid})")


def public_ip() -> str | None:
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                ip = resp.read().decode("utf-8").strip()
                if ip and all(p.isdigit() for p in ip.split(".")):
                    return ip
        except Exception:
            continue
    return None


def ensure_ip_excludes(counter_id: int) -> None:
    ips: list[str] = []
    raw = os.environ.get("YANDEX_METRIKA_EXCLUDE_IPS", "").strip()
    if raw:
        ips.extend(p.strip() for p in raw.replace(";", ",").split(",") if p.strip())
    if os.environ.get("YANDEX_METRIKA_EXCLUDE_MY_IP", "1").strip() not in ("0", "false", "no"):
        mine = public_ip()
        if mine:
            ips.append(mine)
            print(f"  my public IP: {mine}")
    # unique preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for ip in ips:
        if ip not in seen:
            seen.add(ip)
            uniq.append(ip)
    if not uniq:
        print("  IP excludes: none configured")
        return

    existing = api("GET", f"/counter/{counter_id}/filters").get("filters") or []
    have = {
        (f.get("attr"), f.get("type"), f.get("value"), f.get("action"))
        for f in existing
    }
    for ip in uniq:
        key = ("client_ip", "equal", ip, "exclude")
        if key in have:
            print(f"  IP exclude ok: {ip}")
            continue
        out = api(
            "POST",
            f"/counter/{counter_id}/filters",
            {
                "filter": {
                    "attr": "client_ip",
                    "type": "equal",
                    "value": ip,
                    "action": "exclude",
                    "status": "active",
                }
            },
        )
        print(f"  IP exclude created: {ip} id={(out.get('filter') or {}).get('id')}")


def ensure_cut_params(counter_id: int) -> None:
    existing = api("GET", f"/counter/{counter_id}/operations").get("operations") or []
    have = {
        (op.get("action"), op.get("attr"), (op.get("value") or "").lower())
        for op in existing
    }
    for param in CUT_URL_PARAMS:
        key = ("cut_parameter", "url", param.lower())
        if key in have:
            print(f"  cut_parameter ok: {param}")
            continue
        out = api(
            "POST",
            f"/counter/{counter_id}/operations",
            {
                "operation": {
                    "action": "cut_parameter",
                    "attr": "url",
                    "value": param,
                    "status": "active",
                }
            },
        )
        print(f"  cut_parameter created: {param} id={(out.get('operation') or {}).get('id')}")


def main() -> int:
    load_dotenv_files()
    host = site_host()
    print(f"site={host}")
    counter = find_counter(host)
    if counter:
        print(f"found counter id={counter.get('id')} name={counter.get('name')!r}")
    else:
        print("creating counter…")
        created = create_counter(host)
        counter = created.get("counter") or created
        print(f"created counter id={counter.get('id')}")

    cid = int(counter["id"])
    print("settings:")
    ensure_counter_settings(cid)
    print("goals:")
    goals = list_goals(cid)
    for ident, title in GOALS:
        ensure_action_goal(cid, ident, title, goals)
        goals = list_goals(cid)
    print("filters:")
    ensure_ip_excludes(cid)
    print("operations:")
    ensure_cut_params(cid)

    print()
    print(f"YANDEX_METRIKA_COUNTER_ID={cid}")
    print("Добавьте эту строку в secrets/yandex-metrika.env и /opt/sfrfr/.env")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
