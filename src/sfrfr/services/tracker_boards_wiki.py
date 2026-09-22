"""Оркестрация: ensure досок Tracker + Wiki-индекса SFRFR."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

BOARD_SPECS: tuple[dict[str, str], ...] = (
    {
        "queue": "SFRFR",
        "name": "SFRFR",
        "seed_issue": "SFRFR-3",
    },
    {
        "queue": "PUB",
        "name": "PUB",
        "seed_issue": "PUB-5",
    },
    {
        "queue": "FUNNEL",
        "name": "FUNNEL",
        "seed_issue": "FUNNEL-4",
    },
)

WIKI_INDEX_SLUG_DEFAULT = "sfrfr"
WIKI_INDEX_TITLE = "SFRFR — индекс ops"
WIKI_SEED_ISSUE = "SFRFR-5"

WIKI_INDEX_BODY = """# SFRFR — индекс

Канон в git (без ПДн):

- `docs/TRACKER/` — очереди, playbook агентов
- `docs/ops/` — деплой, SLA, техдолг, реанимация
- `docs/AMO/` — резерв amoCRM
- `docs/marketing-sales/` — маркетинг и продажи
- `docs/VK/` — ВКонтакте
- `docs/brand/` — бренд-платформа

Авто: `sfrfr tech-debt-due-tick` (ensure досок + эта страница).
"""


def find_board_for_queue(
    boards: list[dict[str, Any]],
    *,
    queue: str,
    name: str,
) -> dict[str, Any] | None:
    q = queue.strip().upper()
    n = name.strip()
    for b in boards:
        dq = b.get("defaultQueue") or {}
        key = str(dq.get("key") or "").upper()
        bname = str(b.get("name") or "").strip()
        if key == q or bname == n or bname.upper() == q:
            return b
    return None


def ensure_boards_enabled(*, force: bool | None = None) -> bool:
    if force is not None:
        return bool(force)
    raw = (os.environ.get("TECH_DEBT_ENSURE_BOARDS") or "1").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def ensure_wiki_enabled(*, force: bool | None = None) -> bool:
    if force is not None:
        return bool(force)
    raw = (os.environ.get("TECH_DEBT_ENSURE_WIKI") or "1").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def wiki_index_slug() -> str:
    return (os.environ.get("WIKI_SFRFR_SLUG") or WIKI_INDEX_SLUG_DEFAULT).strip().strip("/")


def run_ensure_boards_and_wiki(
    *,
    dry_run: bool = False,
    notify_seed: bool = True,
    force_boards: bool | None = None,
    force_wiki: bool | None = None,
    list_boards_fn: Callable[[], list[dict[str, Any]]] | None = None,
    create_board_fn: Callable[..., dict[str, Any]] | None = None,
    get_wiki_fn: Callable[[str], dict[str, Any] | None] | None = None,
    create_wiki_fn: Callable[..., dict[str, Any]] | None = None,
    add_comment_fn: Callable[[str, str], bool] | None = None,
) -> dict[str, Any]:
    """Идемпотентно создать доски SFRFR/PUB/FUNNEL и Wiki-индекс."""
    stats: dict[str, Any] = {
        "dry_run": dry_run,
        "boards": [],
        "wiki": {"action": "skipped"},
        "comments": [],
    }
    do_boards = ensure_boards_enabled(force=force_boards)
    do_wiki = ensure_wiki_enabled(force=force_wiki)

    list_boards = list_boards_fn or _default_list_boards
    create_board = create_board_fn or _default_create_board
    get_wiki = get_wiki_fn or _default_get_wiki
    create_wiki = create_wiki_fn or _default_create_wiki
    add_comment = add_comment_fn or _default_add_comment

    if do_boards:
        existing = list_boards()
        for spec in BOARD_SPECS:
            found = find_board_for_queue(existing, queue=spec["queue"], name=spec["name"])
            if found:
                bid = found.get("id")
                url = f"https://tracker.yandex.ru/{spec['queue']}/agile/{bid}"
                stats["boards"].append(
                    {
                        "queue": spec["queue"],
                        "action": "exists",
                        "id": bid,
                        "url": url,
                    }
                )
                continue
            if dry_run:
                stats["boards"].append({"queue": spec["queue"], "action": "would_create"})
                continue
            created = create_board(
                name=spec["name"],
                queue=spec["queue"],
            )
            row: dict[str, Any] = {
                "queue": spec["queue"],
                "action": "created" if created.get("ok") else "failed",
                "id": created.get("id"),
                "url": created.get("url"),
                "error": created.get("error"),
            }
            stats["boards"].append(row)
            if created.get("ok") and notify_seed and not dry_run:
                text = (
                    f"## Авто: доска создана через API\n\n"
                    f"- URL: {created.get('url')}\n"
                    f"- Очередь по умолчанию: `{spec['queue']}`\n"
                    f"- Канон: docs/TRACKER/ops-board-wiki-checklist.md\n"
                    f"Скрин владельца больше не обязателен для закрытия seed.\n"
                    f"Фильтр/колонки при необходимости — вручную в UI.\n"
                )
                ok = add_comment(spec["seed_issue"], text)
                stats["comments"].append(
                    {"key": spec["seed_issue"], "action": "ok" if ok else "failed"}
                )
    else:
        stats["boards"].append({"action": "skipped_flag_off"})

    if do_wiki:
        slug = wiki_index_slug()
        page = get_wiki(slug)
        if page:
            stats["wiki"] = {
                "action": "exists",
                "slug": page.get("slug") or slug,
                "url": f"https://wiki.yandex.ru/{(page.get('slug') or slug)}",
            }
        elif dry_run:
            stats["wiki"] = {"action": "would_create", "slug": slug}
        else:
            created_w = create_wiki(
                slug=slug,
                title=WIKI_INDEX_TITLE,
                content=WIKI_INDEX_BODY,
            )
            if created_w.get("ok"):
                stats["wiki"] = {
                    "action": "created",
                    "slug": created_w.get("slug") or slug,
                    "url": created_w.get("url"),
                }
                if notify_seed:
                    text = (
                        f"## Авто: Wiki-индекс создан через API\n\n"
                        f"- URL: {created_w.get('url')}\n"
                        f"- Slug: `{created_w.get('slug') or slug}`\n"
                        f"Без ПДн. Канон: docs/TRACKER/ops-board-wiki-checklist.md\n"
                    )
                    ok = add_comment(WIKI_SEED_ISSUE, text)
                    stats["comments"].append(
                        {"key": WIKI_SEED_ISSUE, "action": "ok" if ok else "failed"}
                    )
            else:
                code = created_w.get("status_code")
                soft = code in (401, 403) or "Forbidden" in str(created_w.get("error") or "")
                stats["wiki"] = {
                    "action": "soft_skip" if soft else "failed",
                    "status_code": code,
                    "error": created_w.get("error"),
                    "hint": (
                        "Нужен OAuth scope wiki:write (WIKI_TOKEN или обновить TRACKER_TOKEN)"
                        if soft
                        else None
                    ),
                }
    else:
        stats["wiki"] = {"action": "skipped_flag_off"}

    return stats


def _default_list_boards() -> list[dict[str, Any]]:
    from sfrfr.integrations.yandex_tracker.boards import list_boards

    return list_boards()


def _default_create_board(**kwargs: Any) -> dict[str, Any]:
    from sfrfr.integrations.yandex_tracker.boards import create_board

    return create_board(**kwargs)


def _default_get_wiki(slug: str) -> dict[str, Any] | None:
    from sfrfr.integrations.yandex_wiki import get_page_by_slug

    return get_page_by_slug(slug)


def _default_create_wiki(**kwargs: Any) -> dict[str, Any]:
    from sfrfr.integrations.yandex_wiki import create_page

    return create_page(**kwargs)


def _default_add_comment(issue_key: str, text: str) -> bool:
    from sfrfr.integrations.yandex_tracker import add_issue_comment

    return bool(add_issue_comment(issue_key, text).get("ok"))
