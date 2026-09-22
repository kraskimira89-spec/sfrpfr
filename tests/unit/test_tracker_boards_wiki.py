"""Ensure досок Tracker и Wiki-индекса (без живого API)."""

from __future__ import annotations

from sfrfr.services.tracker_boards_wiki import (
    BOARD_SPECS,
    WIKI_INDEX_BODY,
    find_board_for_queue,
    run_ensure_boards_and_wiki,
)


def test_board_specs_cover_three_queues() -> None:
    keys = {s["queue"] for s in BOARD_SPECS}
    assert keys == {"SFRFR", "PUB", "FUNNEL"}


def test_find_board_by_queue_key_or_name() -> None:
    boards = [
        {"id": 1, "name": "Other", "defaultQueue": {"key": "STAZH"}},
        {"id": 42, "name": "SFRFR", "defaultQueue": {"key": "SFRFR"}},
    ]
    found = find_board_for_queue(boards, queue="SFRFR", name="SFRFR")
    assert found is not None
    assert found["id"] == 42
    assert find_board_for_queue(boards, queue="PUB", name="PUB") is None


def test_wiki_index_has_doc_paths_no_pii() -> None:
    assert "docs/TRACKER/" in WIKI_INDEX_BODY
    assert "docs/ops/" in WIKI_INDEX_BODY
    assert "@" not in WIKI_INDEX_BODY


def test_run_ensure_dry_run_plans_create() -> None:
    stats = run_ensure_boards_and_wiki(
        dry_run=True,
        list_boards_fn=lambda: [],
        create_board_fn=lambda **_: {"ok": True, "id": 1},
        get_wiki_fn=lambda _slug: None,
        create_wiki_fn=lambda **_: {"ok": True, "slug": "sfrfr"},
        add_comment_fn=lambda _k, _t: True,
    )
    assert all(b["action"] == "would_create" for b in stats["boards"])
    assert stats["wiki"]["action"] == "would_create"
    assert stats["comments"] == []


def test_run_ensure_skips_existing_board_and_wiki() -> None:
    boards = [{"id": 7, "name": "SFRFR", "defaultQueue": {"key": "SFRFR"}}]
    created: list[dict] = []
    wiki_created: list[dict] = []
    comments: list[tuple[str, str]] = []

    def list_boards():
        return boards + [
            {"id": 8, "name": "PUB", "defaultQueue": {"key": "PUB"}},
            {"id": 9, "name": "FUNNEL", "defaultQueue": {"key": "FUNNEL"}},
        ]

    stats = run_ensure_boards_and_wiki(
        dry_run=False,
        list_boards_fn=list_boards,
        create_board_fn=lambda **kw: created.append(kw) or {"ok": True, "id": 99},
        get_wiki_fn=lambda _slug: {"id": 1, "slug": "sfrfr"},
        create_wiki_fn=lambda **kw: wiki_created.append(kw) or {"ok": True},
        add_comment_fn=lambda k, t: comments.append((k, t)) or True,
        notify_seed=True,
    )
    assert created == []
    assert wiki_created == []
    assert all(b["action"] == "exists" for b in stats["boards"])
    assert stats["wiki"]["action"] == "exists"
    # seed-комменты только при создании
    assert comments == []
