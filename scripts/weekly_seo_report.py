#!/usr/bin/env python3
"""Еженедельный SEO-отчёт: комментарий в Трекер (SFRFR-63) и письмо владельцу.

Берёт снимок статусов из yandex_webmaster_url_status.py (--save-baseline tmp/...json),
сравнивает с базовым снимком и добавляет проблемы apex из отчёта диагностики Вебмастера.
Без ПДн и поисковых запросов посетителей.

Env (секреты, не печатаются):
  TRACKER_TOKEN + TRACKER_ORG_ID | TRACKER_CLOUD_ORG_ID — комментарий в Трекер;
  SMTP_USER + SMTP_PASSWORD (пароль приложения Яндекс Почты) — письмо; нет → пропуск.
  REPORT_EMAIL_TO — получатель (не секрет).

Usage:
  python scripts/weekly_seo_report.py --snapshot tmp/seo-page-status.json
  python scripts/weekly_seo_report.py --snapshot tmp/seo-page-status.json --dry-run
"""
from __future__ import annotations

import argparse
import html
import json
import os
import smtplib
import ssl
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import date
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yandex_webmaster_url_status as us  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "docs/marketing-sales/reports"
TRACKER_API = "https://api.tracker.yandex.net/v3"
ISSUE = "SFRFR-63"
DEFAULT_TO = "proverkastaza@yandex.ru"


def summarize(snap: dict[str, Any], base: dict[str, Any] | None) -> dict[str, Any]:
    rows = snap["urls"]
    return {
        "ok": sum(1 for r in rows if r.get("ok")),
        "total": len(rows),
        "low_quality": [us._path(r["url"]) for r in rows if r.get("excluded") == "LOW_QUALITY"],
        "changes": us.diff(base, snap) if base else [],
    }


def apex_problems(diag_md: str) -> list[str]:
    section = diag_md.split("## Apex (действия)", 1)[-1].split("\n## ", 1)[0]
    out = []
    for line in section.splitlines():
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[1] and cells[0] not in ("severity",) and "---" not in cells[0]:
            out.append(f"{cells[0]} {cells[1]} — {cells[3]}")
    return out


def _change_lines(changes: list[tuple[str, list[tuple[str, str, str]]]]) -> list[str]:
    return [
        f"{us._path(url)} — " + "; ".join(f"{k}: {a} → {b}" for k, a, b in items)
        for url, items in changes
    ]


def _summary_lines(
    s: dict[str, Any], problems: list[str], base: dict[str, Any] | None
) -> list[str]:
    since = f" с базового снимка {base['generated'][:10]}" if base else ""
    lines = [f"В целевом статусе: {s['ok']} из {s['total']} страниц.", "", f"Изменения{since}:"]
    lines += [f"- {x}" for x in _change_lines(s["changes"])] or ["- изменений нет"]
    lines += ["", "Ещё LOW_QUALITY:"]
    lines += [f"- {p}" for p in s["low_quality"]] or ["- нет"]
    lines += ["", "Проблемы диагностики Вебмастера (apex):"]
    lines += [f"- {p}" for p in problems] or ["- нет"]
    return lines


def comment_text(
    snap: dict[str, Any], base: dict[str, Any] | None, problems: list[str], run_url: str, day: str
) -> str:
    s = summarize(snap, base)
    head = [f"**Еженедельный SEO-отчёт {day}**", ""] + _summary_lines(s, problems, base)
    if run_url:
        head += ["", f"Run: {run_url}"]
    return "\n".join(head) + "\n\n" + us.render_markdown(snap, base)


def _html_table(snap: dict[str, Any]) -> str:
    rows = []
    for r in snap["urls"]:
        f = us._fields(r)
        cells = [us._path(r["url"]), f["статус"], f["обход"], f["переобход"], f["ответ"], f["цель"]]
        rows.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in cells) + "</tr>")
    head = "".join(
        f"<th>{h}</th>" for h in ("URL", "Статус", "Обход", "Переобход", "Ответ", "Цель")
    )
    return (
        '<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse">'
        f"<tr>{head}</tr>{''.join(rows)}</table>"
    )


def build_email(
    snap: dict[str, Any],
    base: dict[str, Any] | None,
    *,
    to: str,
    sender: str,
    run_url: str,
    issue: str,
    problems: list[str],
    day: str,
) -> EmailMessage:
    s = summarize(snap, base)
    lines = _summary_lines(s, problems, base)
    links = [f"Задача в Трекере: https://tracker.yandex.ru/{issue}"]
    if run_url:
        links.append(f"Run GitHub Actions: {run_url}")
    table = [
        f"{us._path(r['url'])} | {' | '.join(us._fields(r).values())}" for r in snap["urls"]
    ]
    text = "\n".join(lines + ["", *links, "", "URL | статус | обход | переобход | ответ | цель"])
    text += "\n" + "\n".join(table) + "\n"
    body_html = "".join(
        f"<p>{html.escape(x)}</p>" if x and not x.startswith("- ") else
        (f"<li>{html.escape(x[2:])}</li>" if x else "")
        for x in lines + [""] + links
    )
    msg = EmailMessage()
    msg["Subject"] = f"Проверка стажа: еженедельный SEO-отчёт {day}"
    msg["From"] = formataddr(("Проверка стажа — SEO", sender))
    msg["To"] = to
    msg.set_content(text)
    msg.add_alternative(f"<html><body>{body_html}{_html_table(snap)}</body></html>", subtype="html")
    return msg


def tracker_headers(env: dict[str, str]) -> dict[str, str]:
    token = env.get("TRACKER_TOKEN", "")
    if not token:
        raise ValueError("TRACKER_TOKEN не задан")
    headers = {"Authorization": f"OAuth {token}", "Content-Type": "application/json"}
    if org := env.get("TRACKER_CLOUD_ORG_ID"):
        headers["X-Cloud-Org-ID"] = org
    elif org := env.get("TRACKER_ORG_ID"):
        headers["X-Org-ID"] = org
    else:
        raise ValueError("Нужен TRACKER_ORG_ID или TRACKER_CLOUD_ORG_ID")
    return headers


def post_comment(
    issue: str, text: str, env: dict[str, str], opener: Callable[..., Any] = urllib.request.urlopen
) -> int:
    req = urllib.request.Request(
        f"{TRACKER_API}/issues/{issue}/comments",
        data=json.dumps({"text": text}, ensure_ascii=False).encode("utf-8"),
        headers=tracker_headers(env),
        method="POST",
    )
    try:
        with opener(req, timeout=30) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as e:
        return int(e.code)


def send_email(msg: EmailMessage, env: dict[str, str], smtp_cls: Any = smtplib.SMTP_SSL) -> str:
    user, password = env.get("SMTP_USER", ""), env.get("SMTP_PASSWORD", "")
    if not (user and password):
        return "skipped: нет SMTP_USER/SMTP_PASSWORD"
    host = env.get("SMTP_HOST") or "smtp.yandex.ru"
    port = int(env.get("SMTP_PORT") or 465)
    with smtp_cls(host, port, context=ssl.create_default_context(), timeout=30) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)
    return "sent"


def _latest_diag() -> str:
    files = sorted(REPORTS.glob("webmaster-diagnostics-*.md"))
    return files[-1].read_text(encoding="utf-8") if files else ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Еженедельный SEO-отчёт в Трекер и на почту")
    parser.add_argument("--snapshot", type=Path, required=True, help="JSON текущего снимка")
    parser.add_argument("--baseline", type=Path, default=us.BASELINE)
    parser.add_argument("--diag", type=Path, help="отчёт диагностики Вебмастера (md)")
    parser.add_argument("--issue", default=ISSUE)
    parser.add_argument("--dry-run", action="store_true", help="только напечатать комментарий")
    args = parser.parse_args()

    env = dict(os.environ)
    snap = json.loads(args.snapshot.read_text(encoding="utf-8"))
    base = None
    if args.baseline.is_file():
        base = json.loads(args.baseline.read_text(encoding="utf-8"))
    diag = _latest_diag()
    if args.diag and args.diag.is_file():
        diag = args.diag.read_text(encoding="utf-8")
    problems = apex_problems(diag)
    day = date.today().isoformat()
    run_id = env.get("GITHUB_RUN_ID")
    run_url = (
        f"{env.get('GITHUB_SERVER_URL')}/{env.get('GITHUB_REPOSITORY')}/actions/runs/{run_id}"
        if run_id else ""
    )
    text = comment_text(snap, base, problems, run_url, day)
    if args.dry_run:
        sys.stdout.write(text)
        return 0

    report, failed = [], False
    try:
        code = post_comment(args.issue, text, env)
        failed |= code not in (200, 201)
        report.append(f"Трекер {args.issue}: HTTP {code}")
    except ValueError as e:
        failed = True
        report.append(f"Трекер: {e}")

    to = env.get("REPORT_EMAIL_TO") or DEFAULT_TO
    msg = build_email(snap, base, to=to, sender=env.get("SMTP_USER") or to, run_url=run_url,
                      issue=args.issue, problems=problems, day=day)
    try:
        mail = send_email(msg, env)
    except (smtplib.SMTPException, OSError) as e:
        failed, mail = True, f"ошибка {type(e).__name__}"
    report.append(f"Почта {to}: {mail}")
    if mail.startswith("skipped"):
        print(f"::warning::Письмо не отправлено — {mail}")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    block = "\n### Еженедельный отчёт\n\n" + "\n".join(f"- {x}" for x in report) + "\n"
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(block)
    print(block)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
