#!/usr/bin/env python3
"""Создать в Яндекс Календаре события публикации постов Яндекс Бизнеса.

Каждое событие содержит:
- текст поста для копирования;
- пояснение и ссылку на кабинет публикаций Sprav.

Env: secrets/SFRFR_yandex_kalendar.env (YANDEX_CALENDAR_OAUTH_*)
     или YANDEX_OAUTH_* / YANDEX_WORKSPACE_EMAIL
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
POSTS_MD = ROOT / "scripts" / "assets" / "yandex-business" / "posts.md"
SPRAV_POSTS = "https://yandex.ru/sprav/234170727274/p/edit/posts/"
CALDAV = "https://caldav.yandex.ru/calendars/{email}/events-default/"
MSK = timezone(timedelta(hours=3))


def load_env() -> None:
    for rel in (
        "secrets/SFRFR_yandex_kalendar.env",
        "secrets/yandex-workspace.env",
        ".env",
    ):
        path = ROOT / rel
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            k, v = raw.split("=", 1)
            k, v = k.strip(), v.strip().strip("\"'")
            if k and k not in os.environ:
                os.environ[k] = v


def token() -> str:
    for key in (
        "YANDEX_CALENDAR_OAUTH_ACCESS_TOKEN",
        "YANDEX_OAUTH_ACCESS_TOKEN",
    ):
        t = (os.environ.get(key) or "").strip()
        if t.startswith("y0"):
            return t
    raise SystemExit("Нужен YANDEX_CALENDAR_OAUTH_ACCESS_TOKEN или YANDEX_OAUTH_ACCESS_TOKEN")


def email() -> str:
    return (os.environ.get("YANDEX_WORKSPACE_EMAIL") or "proverkastaza@yandex.ru").strip()


def parse_posts(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    chunks = re.split(r"\n## Пост\s+(\d+)\s+[—\-]\s+([^\n]+)\n", text)
    # chunks: preamble, num, title, body, num, title, body, ...
    posts: list[dict[str, str]] = []
    i = 1
    while i + 2 < len(chunks):
        num, title, body = chunks[i], chunks[i + 1], chunks[i + 2]
        body = body.strip()
        if body.endswith("---"):
            body = body[: body.rfind("---")].strip()
        theme_m = re.search(r"\*\*Тема:\*\*\s*(.+)", body)
        theme = (theme_m.group(1).strip() if theme_m else title.strip())
        posts.append(
            {
                "num": num.strip(),
                "label": title.strip(),
                "theme": theme,
                "body": body,
            }
        )
        i += 3
    if len(posts) < 8:
        raise SystemExit(f"Ожидалось 8 постов, разобрано {len(posts)}")
    return posts[:8]


def ics_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
    )


def ics_fold(line: str) -> str:
    """Свернуть длинную строку ICS (~75 байт UTF-8)."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts: list[str] = []
    while raw:
        cut = 75 if not parts else 74
        chunk = raw[:cut]
        while True:
            try:
                chunk.decode("utf-8")
                break
            except UnicodeDecodeError:
                cut -= 1
                chunk = raw[:cut]
        parts.append(chunk.decode("utf-8"))
        raw = raw[cut:]
    out = parts[0]
    for p in parts[1:]:
        out += "\r\n " + p
    return out


def build_description(post: dict[str, str]) -> str:
    return (
        "ПОЯСНЕНИЕ\n"
        "Опубликуйте этот пост вручную в Яндекс Бизнесе (раздел Публикации).\n"
        f"Кабинет: {SPRAV_POSTS}\n"
        "Шаги: Создать → вставить текст ниже → отправить на модерацию.\n"
        "Ссылки только на proverkastaza.ru; без гарантий перерасчёта.\n"
        "\n"
        "——— ТЕКСТ ДЛЯ ПУБЛИКАЦИИ ———\n"
        f"{post['body']}\n"
    )


def schedule_starts() -> list[datetime]:
    """По средам 10:00 МСК, начиная с ближайшей среды (не раньше завтра)."""
    now = datetime.now(MSK)
    # ближайшая среда
    days_ahead = (2 - now.weekday()) % 7  # Wed=2
    first = (now + timedelta(days=days_ahead)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    if first.date() <= now.date():
        first += timedelta(days=7)
    return [first + timedelta(weeks=i) for i in range(8)]


def put_event(
    *,
    access: str,
    mail: str,
    start: datetime,
    summary: str,
    description: str,
    duration_minutes: int = 30,
) -> dict:
    end = start + timedelta(minutes=duration_minutes)
    uid = f"{uuid.uuid4()}@sfrfr-yandex-business"
    stamp = datetime.now(timezone.utc)

    def fmt(dt: datetime) -> str:
        return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SFRFR//Yandex Business Posts//RU",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{fmt(stamp)}",
        f"DTSTART:{fmt(start)}",
        f"DTEND:{fmt(end)}",
        ics_fold(f"SUMMARY:{ics_escape(summary)}"),
        ics_fold(f"DESCRIPTION:{ics_escape(description)}"),
        f"URL:{SPRAV_POSTS}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    ical = "\r\n".join(lines) + "\r\n"
    base = CALDAV.format(email=mail)
    event_url = f"{base}{uid}.ics"
    headers = {
        "Authorization": f"OAuth {access}",
        "Content-Type": "text/calendar; charset=utf-8",
    }
    with httpx.Client(timeout=40.0) as client:
        resp = client.put(event_url, headers=headers, content=ical.encode("utf-8"))
    return {
        "ok": resp.status_code in (200, 201, 204),
        "status_code": resp.status_code,
        "uid": uid,
        "starts_at": start.isoformat(),
        "summary": summary,
        "detail": (resp.text or "")[:200] if resp.status_code not in (200, 201, 204) else "",
    }


def main() -> int:
    load_env()
    access = token()
    mail = email()
    posts = parse_posts(POSTS_MD)
    starts = schedule_starts()
    print(f"email={mail} posts={len(posts)} first={starts[0].isoformat()}")
    ok_n = 0
    for post, start in zip(posts, starts, strict=True):
        summary = f"Яндекс Бизнес: пост {post['num']} — {post['theme']}"[:180]
        desc = build_description(post)
        result = put_event(
            access=access,
            mail=mail,
            start=start,
            summary=summary,
            description=desc,
        )
        status = "OK" if result["ok"] else "FAIL"
        print(f"{status} {result['starts_at']} {summary} [{result['status_code']}] {result.get('detail','')}")
        if result["ok"]:
            ok_n += 1
    print(f"done ok={ok_n}/{len(posts)} cabinet={SPRAV_POSTS}")
    return 0 if ok_n == len(posts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
