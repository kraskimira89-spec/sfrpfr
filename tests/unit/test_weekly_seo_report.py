"""Еженедельный SEO-отчёт: комментарий в Трекер и письмо (моки Трекера и SMTP)."""

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts import weekly_seo_report as wr  # noqa: E402

BASE = "https://proverkastaza.ru"


def _row(path: str, in_search: bool, excluded: str | None, ok: bool, crawl: str) -> dict[str, Any]:
    return {
        "url": f"{BASE}{path}",
        "group": "PR #101",
        "expected": "in_search",
        "in_search": in_search,
        "excluded": excluded,
        "last_crawl": crawl,
        "recrawl": "DONE",
        "live": {"code": 200, "location": None, "noindex": False},
        "ok": ok,
    }


BASELINE = {
    "generated": "2026-09-27T21:05+05:00",
    "urls": [
        _row("/blog/ils/", False, "LOW_QUALITY", False, "2026-09-04"),
        _row("/blog/lgot/", False, "LOW_QUALITY", False, "2026-08-23"),
        _row("/tarify/", True, None, True, "2026-09-26"),
    ],
}
CURRENT = {
    "generated": "2026-10-05T09:15+03:00",
    "urls": [
        _row("/blog/ils/", True, None, True, "2026-10-01"),
        _row("/blog/lgot/", False, "LOW_QUALITY", False, "2026-08-23"),
        _row("/tarify/", True, None, True, "2026-09-26"),
    ],
}
DIAG = """# Диагностика
## Apex (действия)

- searchable_pages: **24**

| severity | код | обновлено | что делать |
|----------|-----|-----------|------------|
| FATAL | `DISALLOWED_IN_ROBOTS` | 2026-10-05 | robots |

## Все хосты (справка)
- `NO_REGIONS` (RECOMMENDATION) _(зеркало, можно игнорировать)_
"""
ENV = {"TRACKER_TOKEN": "tok", "TRACKER_ORG_ID": "42"}


class FakeResp:
    status = 201

    def __enter__(self) -> "FakeResp":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return b"{}"


def test_summary_counts_changes_and_low_quality() -> None:
    s = wr.summarize(CURRENT, BASELINE)
    assert (s["ok"], s["total"]) == (2, 3)
    assert s["low_quality"] == ["/blog/lgot/"]
    assert [url for url, _ in s["changes"]] == [f"{BASE}/blog/ils/"]


def test_apex_problems_only_from_apex_section() -> None:
    problems = wr.apex_problems(DIAG)
    assert problems == ["FATAL DISALLOWED_IN_ROBOTS — robots"]
    assert wr.apex_problems("## Apex (действия)\n\n✅ Активных проблем на apex **нет**.\n") == []


def test_post_comment_uses_org_header_and_body() -> None:
    seen: dict[str, Any] = {}

    def opener(req: Any, timeout: int = 0) -> FakeResp:
        seen["url"] = req.full_url
        seen["headers"] = {k.lower(): v for k, v in req.header_items()}
        seen["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResp()

    assert wr.post_comment("SFRFR-63", "текст", ENV, opener=opener) == 201
    assert seen["url"] == "https://api.tracker.yandex.net/v3/issues/SFRFR-63/comments"
    assert seen["headers"]["authorization"] == "OAuth tok"
    assert seen["headers"]["x-org-id"] == "42"
    assert seen["body"] == {"text": "текст"}


def test_cloud_org_header_preferred() -> None:
    headers = wr.tracker_headers({"TRACKER_TOKEN": "t", "TRACKER_CLOUD_ORG_ID": "bpf"})
    assert headers["X-Cloud-Org-ID"] == "bpf" and "X-Org-ID" not in headers


def test_email_subject_body_and_table() -> None:
    msg = wr.build_email(
        CURRENT,
        BASELINE,
        to="proverkastaza@yandex.ru",
        sender="robot@example.ru",
        run_url="https://github.com/x/y/actions/runs/1",
        issue="SFRFR-63",
        problems=["FATAL DISALLOWED_IN_ROBOTS — robots"],
        day="2026-10-05",
    )
    assert msg["Subject"] == "Проверка стажа: еженедельный SEO-отчёт 2026-10-05"
    assert msg["To"] == "proverkastaza@yandex.ru"
    plain_part, html_part = msg.get_body(("plain",)), msg.get_body(("html",))
    assert plain_part is not None and html_part is not None
    text, html = plain_part.get_content(), html_part.get_content()
    assert "2 из 3" in text and "/blog/lgot/" in text and "DISALLOWED_IN_ROBOTS" in text
    assert "actions/runs/1" in text and "SFRFR-63" in text
    assert "<table" in html and "/blog/ils/" in html


class FakeSMTP:
    sent: list[Any] = []
    logins: list[tuple[str, str]] = []

    def __init__(self, host: str, port: int, **kw: Any) -> None:
        assert (host, port) == ("smtp.yandex.ru", 465)

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def login(self, user: str, password: str) -> None:
        FakeSMTP.logins.append((user, password))

    def send_message(self, msg: Any) -> None:
        FakeSMTP.sent.append(msg)


def _msg() -> Any:
    return wr.build_email(
        CURRENT, BASELINE, to="a@b.ru", sender="s@b.ru", run_url="", issue="SFRFR-63",
        problems=[], day="2026-10-05",
    )


def test_send_email_skips_without_smtp_secrets() -> None:
    FakeSMTP.sent.clear()
    assert wr.send_email(_msg(), {}, smtp_cls=FakeSMTP).startswith("skipped")
    assert FakeSMTP.sent == []


def test_send_email_with_app_password() -> None:
    FakeSMTP.sent.clear()
    FakeSMTP.logins.clear()
    env = {"SMTP_USER": "proverkastaza@yandex.ru", "SMTP_PASSWORD": "app-pass"}
    assert wr.send_email(_msg(), env, smtp_cls=FakeSMTP) == "sent"
    assert FakeSMTP.logins == [("proverkastaza@yandex.ru", "app-pass")]
    assert len(FakeSMTP.sent) == 1
