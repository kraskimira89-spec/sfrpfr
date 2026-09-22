"""Автоматизация техдолга: snapshot / ensure / comments."""

from __future__ import annotations

from datetime import UTC, datetime

from sfrfr.services.tech_debt_automation import (
    build_reminder_text,
    comment_has_week_marker,
    iso_week_key,
    run_due_tick,
    should_skip_comment,
    tick_marker,
)


def test_iso_week_and_marker() -> None:
    week = iso_week_key(datetime(2026, 9, 22, 12, 0, tzinfo=UTC))
    assert week == "2026-W39"
    assert "2026-W39" in tick_marker(week)
    assert comment_has_week_marker(f"hello {tick_marker(week)}", week)
    assert not comment_has_week_marker("hello", week)


def test_should_skip_same_week() -> None:
    week = "2026-W39"
    assert should_skip_comment(existing_texts=[f"x {tick_marker(week)}"], week=week)
    assert not should_skip_comment(existing_texts=["other"], week=week)


def test_build_reminder_contains_marker_and_counts() -> None:
    text = build_reminder_text(
        week="2026-W39",
        body="## Hello",
        snapshot_counts={"FUNNEL": 5, "SFRFR": 3},
    )
    assert "## Hello" in text
    assert "FUNNEL=5" in text
    assert tick_marker("2026-W39") in text


def test_run_due_tick_dry_run_plans_ensure_and_comments(tmp_path) -> None:
    created: list[dict] = []
    comments: list[tuple[str, str]] = []

    def list_open():
        return {"STAZH": [], "SFRFR": [{"key": "SFRFR-1"}], "PUB": [], "FUNNEL": []}

    def search_tag(tag: str):
        return None

    def create_issue(**kwargs):
        created.append(kwargs)
        return {"ok": True, "key": f"SFRFR-NEW-{len(created)}"}

    def list_comments(_key: str):
        return []

    def add_comment(key: str, text: str):
        comments.append((key, text))
        return True

    stats = run_due_tick(
        dry_run=True,
        force_comment=True,
        now=datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
        snapshot_path=tmp_path / "snap.json",
        list_open_fn=list_open,
        search_by_tag_fn=search_tag,
        create_issue_fn=create_issue,
        list_comments_fn=list_comments,
        add_comment_fn=add_comment,
    )
    assert stats["week"] == "2026-W39"
    assert stats["counts"]["SFRFR"] == 1
    assert any(e["action"] == "would_create" for e in stats["ensured"])
    assert any(c["action"] == "would_comment" for c in stats["comments"])
    assert created == []
    assert comments == []


def test_run_due_tick_skips_comment_same_week(tmp_path) -> None:
    week = "2026-W39"

    def list_open():
        return {"STAZH": [], "SFRFR": [], "PUB": [], "FUNNEL": []}

    def list_comments(key: str):
        if key == "FUNNEL-11":
            return [f"already {tick_marker(week)}"]
        return []

    stats = run_due_tick(
        dry_run=False,
        force_comment=True,
        now=datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
        snapshot_path=tmp_path / "snap.json",
        list_open_fn=list_open,
        search_by_tag_fn=lambda _t: "SFRFR-99",
        create_issue_fn=lambda **_k: {"ok": True, "key": "X"},
        list_comments_fn=list_comments,
        add_comment_fn=lambda _k, _t: True,
    )
    funnel11 = next(c for c in stats["comments"] if c["key"] == "FUNNEL-11")
    assert funnel11["action"] == "skip_same_week"
    assert (tmp_path / "snap.json").is_file()
