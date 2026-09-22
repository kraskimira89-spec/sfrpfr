"""Автоматизация техдолга: snapshot Tracker + ensure issues + weekly comments."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TICK_MARKER_PREFIX = "<!-- sfrfr-tech-debt-tick:"
ENSURE_SPECS: tuple[dict[str, str], ...] = (
    {
        "id": "tz13-ingest-acceptance",
        "queue": "SFRFR",
        "summary": "[tech-debt] ТЗ-13: закрыть или вычеркнуть чеклист приёмки ingest v2",
        "description": (
            "Автозадача из docs/ops/tech-debt-2026-09-22.md.\n\n"
            "Канон: docs/specs/13-document-ingest-v2.md § приёмка — много пунктов `[ ]`.\n"
            "Нужно: сверить с кодом и либо закрыть чеклист, либо вычеркнуть устаревшее.\n"
            "Без ПДн в комментариях."
        ),
    },
    {
        "id": "tz09-e2e-parity",
        "queue": "SFRFR",
        "summary": "[tech-debt] ТЗ-09: ручной E2E паритет MAX ↔ веб-кабинет",
        "description": (
            "Автозадача из среза техдолга.\n\n"
            "Runbook: docs/qa/tz09-stage-d.md. Нужен тестовый MAX.\n"
            "Чеклист в docs/specs/09-client-channels-parity.md."
        ),
    },
    {
        "id": "tz15-supabase-cutover",
        "queue": "SFRFR",
        "summary": "[tech-debt] ТЗ-15: решение срока self-host Supabase (YC)",
        "description": (
            "Автозадача из среза техдолга.\n\n"
            "Канон: docs/specs/15-data-localization-ru.md.\n"
            "Owner: зафиксировать дату cutover или явную отсрочку."
        ),
    },
)

REMINDER_ISSUES: tuple[dict[str, str], ...] = (
    {
        "key": "FUNNEL-11",
        "body": (
            "## Авто-напоминание: реанимация\n\n"
            "Чеклист недели — docs/ops/playbook-case-reactivation.md §5.\n"
            "- Timer `sfrfr-case-reactivation.timer`\n"
            "- dry-run / sent / skipped (без ПДн)\n"
            "- Канбан: просроченный next_action_at\n"
        ),
    },
    {
        "key": "FUNNEL-2",
        "body": (
            "## Авто-напоминание: SLA lead/qualify\n\n"
            "Playbook: docs/ops/playbook-funnel-lead-sla.md\n"
            "Заполнить CSV / комментарий за неделю (case_ref = хвост id).\n"
        ),
    },
    {
        "key": "FUNNEL-5",
        "body": (
            "## Авто-напоминание: clarity-разбор\n\n"
            "5–10 диалогов по docs/ops/playbook-funnel-clarity-dialog-review.md\n"
            "Без ПДн в Tracker.\n"
        ),
    },
    {
        "key": "FUNNEL-4",
        "body": (
            "## Авто-напоминание: доска FUNNEL\n\n"
            "Ensure через API: `TECH_DEBT_ENSURE_BOARDS=1` в tech-debt-due-tick.\n"
            "Канон: docs/TRACKER/ops-board-wiki-checklist.md\n"
            "Если доска есть — seed можно закрыть (скрин не обязателен).\n"
        ),
    },
    {
        "key": "SFRFR-3",
        "body": (
            "## Авто-напоминание: доска SFRFR\n\n"
            "Ensure через API (не owner UI). ops-board-wiki-checklist.md\n"
        ),
    },
    {
        "key": "SFRFR-5",
        "body": (
            "## Авто-напоминание: Wiki SFRFR\n\n"
            "Ensure через Wiki API (`TECH_DEBT_ENSURE_WIKI=1`). "
            "Нужен scope wiki:write или WIKI_TOKEN.\n"
        ),
    },
)


def iso_week_key(now: datetime | None = None) -> str:
    dt = (now or datetime.now(UTC)).astimezone(UTC)
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


def tick_marker(week: str) -> str:
    return f"{TICK_MARKER_PREFIX}{week} -->"


def comment_has_week_marker(text: str, week: str) -> bool:
    return tick_marker(week) in (text or "")


def auto_comment_enabled(*, force: bool | None = None) -> bool:
    if force is not None:
        return bool(force)
    raw = (os.environ.get("TECH_DEBT_AUTO_COMMENT") or "1").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def build_reminder_text(*, week: str, body: str, snapshot_counts: dict[str, int]) -> str:
    counts = ", ".join(f"{k}={v}" for k, v in sorted(snapshot_counts.items()))
    return (
        f"{body.strip()}\n\n"
        f"Срез открытых (авто): {counts or 'n/a'}.\n"
        f"Канон: docs/ops/tech-debt-2026-09-22.md · "
        f"docs/ops/playbook-tech-debt-automation.md\n"
        f"{tick_marker(week)}\n"
    )


def should_skip_comment(*, existing_texts: list[str], week: str) -> bool:
    return any(comment_has_week_marker(t, week) for t in existing_texts)


def ensure_spec_tags(spec_id: str) -> list[str]:
    return ["tech-debt-auto", f"tech-debt:{spec_id}"]


def run_due_tick(
    *,
    dry_run: bool = False,
    snapshot_only: bool = False,
    force_comment: bool | None = None,
    now: datetime | None = None,
    snapshot_path: Path | None = None,
    list_open_fn: Any | None = None,
    list_comments_fn: Any | None = None,
    add_comment_fn: Any | None = None,
    create_issue_fn: Any | None = None,
    search_by_tag_fn: Any | None = None,
    ensure_boards_wiki_fn: Any | None = None,
) -> dict[str, Any]:
    """Еженедельный тик техдолга."""
    week = iso_week_key(now)
    do_comment = auto_comment_enabled(force=force_comment)
    stats: dict[str, Any] = {
        "week": week,
        "dry_run": dry_run,
        "snapshot_only": snapshot_only,
        "auto_comment": do_comment,
        "snapshot_ok": False,
        "counts": {},
        "ensured": [],
        "boards_wiki": {},
        "comments": [],
        "skipped": [],
    }

    list_open = list_open_fn or _default_list_open
    open_map = list_open()
    counts = {q: len(items) for q, items in open_map.items()}
    stats["counts"] = counts

    path = snapshot_path or Path("docs/ops/tech-debt-tracker-snapshot.json")
    payload = {
        q: {
            "http": 200,
            "open_n": len(items),
            "issues": items,
        }
        for q, items in open_map.items()
    }
    if not dry_run:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            stats["snapshot_ok"] = True
            stats["snapshot_path"] = str(path)
        except OSError as exc:
            logger.warning("tech_debt_snapshot_failed err=%s", type(exc).__name__)
            stats["snapshot_error"] = type(exc).__name__
    else:
        stats["snapshot_ok"] = True
        stats["snapshot_path"] = str(path)

    if snapshot_only:
        return stats

    create_issue = create_issue_fn or _default_create_issue
    search_tag = search_by_tag_fn or _default_search_by_tag
    for spec in ENSURE_SPECS:
        tag = f"tech-debt:{spec['id']}"
        existing = search_tag(tag)
        if existing:
            stats["ensured"].append({"id": spec["id"], "action": "exists", "key": existing})
            continue
        if dry_run:
            stats["ensured"].append({"id": spec["id"], "action": "would_create"})
            continue
        created = create_issue(
            summary=spec["summary"],
            description=spec["description"],
            tags=ensure_spec_tags(spec["id"]),
            queue=spec["queue"],
        )
        stats["ensured"].append(
            {
                "id": spec["id"],
                "action": "created" if created.get("ok") else "failed",
                "key": created.get("key"),
                "error": created.get("error"),
            }
        )

    ensure_bw = ensure_boards_wiki_fn or _default_ensure_boards_wiki
    stats["boards_wiki"] = ensure_bw(dry_run=dry_run)

    if not do_comment:
        stats["skipped"].append("auto_comment_off")
        return stats

    list_comments = list_comments_fn or _default_list_comments
    add_comment = add_comment_fn or _default_add_comment
    for rem in REMINDER_ISSUES:
        key = rem["key"]
        texts = list_comments(key)
        if should_skip_comment(existing_texts=texts, week=week):
            stats["comments"].append({"key": key, "action": "skip_same_week"})
            continue
        text = build_reminder_text(week=week, body=rem["body"], snapshot_counts=counts)
        if dry_run:
            stats["comments"].append({"key": key, "action": "would_comment"})
            continue
        ok = add_comment(key, text)
        stats["comments"].append({"key": key, "action": "ok" if ok else "failed"})
    return stats


def _default_list_open() -> dict[str, list[dict[str, Any]]]:
    from sfrfr.integrations.yandex_tracker import list_open_issues_by_queues

    return list_open_issues_by_queues(["STAZH", "SFRFR", "PUB", "FUNNEL"])


def _default_list_comments(issue_key: str) -> list[str]:
    from sfrfr.integrations.yandex_tracker import list_issue_comment_texts

    return list_issue_comment_texts(issue_key)


def _default_add_comment(issue_key: str, text: str) -> bool:
    from sfrfr.integrations.yandex_tracker import add_issue_comment

    return bool(add_issue_comment(issue_key, text).get("ok"))


def _default_create_issue(**kwargs: Any) -> dict[str, Any]:
    from sfrfr.integrations.yandex_tracker import create_issue

    return create_issue(
        summary=kwargs["summary"],
        description=kwargs["description"],
        tags=kwargs["tags"],
        queue=kwargs.get("queue"),
        priority="normal",
    )


def _default_search_by_tag(tag: str) -> str | None:
    from sfrfr.integrations.yandex_tracker import find_issue_key_by_tag

    return find_issue_key_by_tag(tag)


def _default_ensure_boards_wiki(*, dry_run: bool = False) -> dict[str, Any]:
    from sfrfr.services.tracker_boards_wiki import run_ensure_boards_and_wiki

    return run_ensure_boards_and_wiki(dry_run=dry_run, notify_seed=not dry_run)
