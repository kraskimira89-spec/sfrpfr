#!/usr/bin/env python3
"""Диагностика Яндекс Вебмастера через API (аналог части email-уведомлений).

Env: secrets/yandex-webmaster.env
  YANDEX_WEBMASTER_OAUTH_ACCESS_TOKEN
  YANDEX_WEBMASTER_HOST_ID=https:proverkastaza.ru:443  (опционально, apex по умолчанию)

Usage:
  python scripts/yandex_webmaster_diagnostics.py
  python scripts/yandex_webmaster_diagnostics.py --all-hosts
  python scripts/yandex_webmaster_diagnostics.py --report
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

API = "https://api.webmaster.yandex.net/v4"
ROOT = Path(__file__).resolve().parents[1]
APEX_HOST_ID = "https:proverkastaza.ru:443"
MSK = ZoneInfo("Europe/Moscow")

PROBLEM_HINTS: dict[str, str] = {
    "DISALLOWED_IN_ROBOTS": "Сайт закрыт в robots.txt — проверить apex /robots.txt",
    "DNS_ERROR": "DNS не резолвится — проверить домен на VPS",
    "MAIN_PAGE_ERROR": "Главная отдаёт ошибку — curl https://proverkastaza.ru/",
    "THREATS": "Угрозы безопасности — раздел «Безопасность» в Вебмастере",
    "SSL_CERTIFICATE_ERROR": "Проблема SSL — certbot / Let's Encrypt",
    "SLOW_AVG_RESPONSE_TIME": "Медленный ответ сервера",
    "ERROR_IN_ROBOTS_TXT": "Ошибка robots.txt — scripts/wp-mu-plugins/sfrfr-seo-robots.php",
    "ERRORS_IN_SITEMAPS": "Ошибки sitemap — wp-sitemap.xml",
    "NO_ROBOTS_TXT": "robots.txt не найден",
    "NO_SITEMAPS": "Нет sitemap — ensure + robots Sitemap:",
    "NO_SITEMAP_MODIFICATIONS": "Sitemap давно не обновлялся",
    "MAIN_PAGE_REDIRECTS": "Главная редиректит (на зеркале www/http — ожидаемо)",
    "MAIN_MIRROR_IS_NOT_HTTPS": "Зеркало не HTTPS (на www/http — ожидаемо)",
    "NO_METRIKA_COUNTER_CRAWL_ENABLED": "UI: включить обход по счётчикам Метрики",
    "NO_METRIKA_COUNTER_BINDING": "UI: привязать счётчик 111134477 к apex",
    "NO_REGIONS": "UI: регион сайта -> Россия (apex)",
    "NOT_IN_SPRAV": "Sprav 82469923047 — привязать организацию в UI",
    "FAVICON_PROBLEM": "Проверить /favicon.ico, /favicon.svg, /favicon-120.png",
    "DOCUMENTS_MISSING_TITLE": "На многих страницах нет title",
    "DOCUMENTS_MISSING_DESCRIPTION": "На многих страницах нет description",
    "SOFT_404": "Неверная отдача 404 для несуществующих страниц",
    "TOO_MANY_PAGE_DUPLICATES": "Много дублей страниц",
    "BAD_ADVERTISEMENT": "Рекламные форматы не по рекомендациям IAB",
}

MIRROR_ONLY = frozenset(
    {
        "MAIN_PAGE_REDIRECTS",
        "MAIN_MIRROR_IS_NOT_HTTPS",
        "NO_REGIONS",
        "NOT_IN_SPRAV",
        "FAVICON_PROBLEM",
    }
)


def load_dotenv() -> None:
    for rel in ("secrets/yandex-webmaster.env", ".env"):
        path = ROOT / rel
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


def api(method: str, path: str) -> tuple[int, dict | list | None]:
    token = os.environ.get("YANDEX_WEBMASTER_OAUTH_ACCESS_TOKEN", "").strip()
    if not token or not token.startswith("y0"):
        raise SystemExit("Нужен YANDEX_WEBMASTER_OAUTH_ACCESS_TOKEN вида y0_…")
    req = urllib.request.Request(
        f"{API}{path}",
        headers={"Authorization": f"OAuth {token}", "Accept": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(err)
        except json.JSONDecodeError:
            parsed = {"raw": err}
        return e.code, parsed


def list_hosts(uid: object) -> list[dict]:
    code, data = api("GET", f"/user/{uid}/hosts")
    if code != 200 or not isinstance(data, dict):
        raise SystemExit(f"hosts {code}: {data}")
    hosts = [h for h in data.get("hosts") or [] if "proverkastaza.ru" in str(h.get("host_id", ""))]
    return hosts


def host_diagnostics(uid: object, host_id: str) -> dict:
    enc = urllib.parse.quote(host_id, safe="")
    code, data = api("GET", f"/user/{uid}/hosts/{enc}/diagnostics")
    if code != 200 or not isinstance(data, dict):
        return {"error": f"diagnostics {code}", "body": data}
    return data


def host_summary(uid: object, host_id: str) -> dict:
    enc = urllib.parse.quote(host_id, safe="")
    code, data = api("GET", f"/user/{uid}/hosts/{enc}/summary")
    if code != 200 or not isinstance(data, dict):
        return {"error": f"summary {code}", "body": data}
    return data


def present_problems(diag: dict) -> list[dict]:
    out: list[dict] = []
    for code, item in sorted((diag.get("problems") or {}).items()):
        if not isinstance(item, dict) or item.get("state") != "PRESENT":
            continue
        out.append(
            {
                "code": code,
                "severity": item.get("severity"),
                "updated": item.get("last_state_update"),
                "hint": PROBLEM_HINTS.get(code, ""),
            }
        )
    return out


def is_actionable(host_id: str, code: str) -> bool:
    if host_id == APEX_HOST_ID:
        return True
    return code not in MIRROR_ONLY


def collect(uid: object, hosts: list[dict]) -> dict:
    rows: list[dict] = []
    for h in hosts:
        hid = str(h.get("host_id") or "")
        url = (h.get("ascii_host_url") or h.get("unicode_host_url") or hid).rstrip("/")
        diag = host_diagnostics(uid, hid)
        summary = host_summary(uid, hid)
        problems = present_problems(diag)
        actionable = [p for p in problems if is_actionable(hid, p["code"])]
        rows.append(
            {
                "host_id": hid,
                "host_url": url,
                "verified": bool(h.get("verified")),
                "summary": summary,
                "problems": problems,
                "actionable": actionable,
            }
        )
    apex = next((r for r in rows if r["host_id"] == APEX_HOST_ID), None)
    return {
        "checked_at": datetime.now(timezone.utc).astimezone(MSK).isoformat(timespec="seconds"),
        "apex_host_id": APEX_HOST_ID,
        "hosts": rows,
        "apex_actionable_count": len(apex["actionable"]) if apex else None,
    }


def print_console(payload: dict) -> None:
    print(f"checked_at={payload['checked_at']}")
    for row in payload["hosts"]:
        print(f"\n== {row['host_url']} ({row['host_id']}) ==")
        summ = row["summary"]
        if "error" in summ:
            print(f"summary ERROR: {summ}")
        else:
            print(
                "summary:",
                f"searchable={summ.get('searchable_pages_count')}",
                f"excluded={summ.get('excluded_pages_count')}",
                f"site_problems={summ.get('site_problems')}",
            )
        if not row["problems"]:
            print("diagnostics: OK (net PRESENT)")
            continue
        for p in row["problems"]:
            tag = "ACTION" if p in row["actionable"] else "mirror/info"
            hint = f" — {p['hint']}" if p["hint"] else ""
            print(f"  [{tag}] {p['severity']} {p['code']} ({p['updated']}){hint}")


def render_markdown(payload: dict) -> str:
    lines = [
        f"# Диагностика Яндекс Вебмастера ({date.today().isoformat()})",
        "",
        f"Снято: `{payload['checked_at']}` · скрипт `scripts/yandex_webmaster_diagnostics.py`",
        "",
        "**Канон:** смотреть только apex `https://proverkastaza.ru` (без www).",
        "Зеркала `www` / `http` с 301 — предупреждения там ожидаемы.",
        "",
        "UI: [диагностика apex](https://webmaster.yandex.ru/site/https%3Aproverkastaza.ru%3A443/diagnostics/)",
        "",
        "## Apex (действия)",
        "",
    ]
    apex = next((r for r in payload["hosts"] if r["host_id"] == APEX_HOST_ID), None)
    if not apex:
        lines.append("_Хост apex не найден в API._")
    else:
        summ = apex["summary"]
        lines.extend(
            [
                f"- searchable_pages: **{summ.get('searchable_pages_count', '?')}**",
                f"- excluded_pages: {summ.get('excluded_pages_count', '?')}",
                f"- site_problems: `{summ.get('site_problems')}`",
                "",
            ]
        )
        if not apex["actionable"]:
            lines.append("✅ Активных проблем на apex **нет**.")
        else:
            lines.append("| severity | код | обновлено | что делать |")
            lines.append("|----------|-----|-----------|------------|")
            for p in apex["actionable"]:
                lines.append(
                    f"| {p['severity']} | `{p['code']}` | {p['updated']} | {p['hint'] or 'см. Вебмастер'} |"
                )
    lines.extend(["", "## Все хосты (справка)", ""])
    for row in payload["hosts"]:
        lines.append(f"### {row['host_url']}")
        if not row["problems"]:
            lines.append("- diagnostics: OK")
        else:
            for p in row["problems"]:
                note = " _(зеркало, можно игнорировать)_" if p not in row["actionable"] else ""
                lines.append(f"- `{p['code']}` ({p['severity']}){note}")
        lines.append("")
    lines.extend(
        [
            "## Как обновить",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\Activate.ps1",
            "python scripts/yandex_webmaster_diagnostics.py --report",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Диагностика Вебмастера через API")
    parser.add_argument(
        "--all-hosts",
        action="store_true",
        help="Все хосты proverkastaza.ru (по умолчанию только apex в отчёте actionable)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help=f"Записать markdown в docs/marketing-sales/reports/webmaster-diagnostics-{date.today()}.md",
    )
    parser.add_argument("--json", action="store_true", help="JSON на stdout")
    args = parser.parse_args()

    load_dotenv()
    code, user = api("GET", "/user")
    if code != 200 or not isinstance(user, dict):
        raise SystemExit(f"user {code}: {user}")
    uid = user["user_id"]

    hosts = list_hosts(uid)
    console_hosts = hosts
    if not args.all_hosts and not args.json:
        console_hosts = [h for h in hosts if str(h.get("host_id")) == APEX_HOST_ID] or hosts[:1]

    payload = collect(uid, console_hosts)
    apex_payload = collect(uid, hosts)

    if args.json:
        print(json.dumps(apex_payload, ensure_ascii=False, indent=2))
    else:
        print_console(payload)

    if args.report:
        out_path = ROOT / "docs/marketing-sales/reports" / f"webmaster-diagnostics-{date.today()}.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(render_markdown(apex_payload), encoding="utf-8")
        print(f"\nreport: {out_path.relative_to(ROOT)}", file=sys.stderr)

    return 1 if (apex_payload.get("apex_actionable_count") or 0) > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
