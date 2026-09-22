"""Синхронизация выбранных docs/*.md в Яндекс Wiki под slug sfrfr/…"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

WIKI_ROOT = "sfrfr"
STAFF_HUB_SLUG = "sfrfr/staff"
MAX_CONTENT_CHARS = 48000

SYNC_GLOBS: tuple[str, ...] = (
    "docs/specs/**/*.md",
    "docs/ops/**/*.md",
    "docs/history/**/*.md",
    "docs/marketing-sales/**/*.md",
)

SKIP_NAME_PARTS: tuple[str, ...] = (
    "conversation.md",
    "project.md",
)

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?7|8)[\s\-()]?\d{3}[\s\-()]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")
_SNILS_RE = re.compile(r"\b\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}\b")
_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.I,
)
_Y0_RE = re.compile(r"\by0_[A-Za-z0-9_-]{20,}\b")
_CABINET_URL_RE = re.compile(
    r"https?://(?:cabinet|admin)\.proverkastaza\.ru[^\s)]*",
    re.I,
)


@dataclass(frozen=True)
class WikiPageSpec:
    slug: str
    title: str
    content: str
    source: str


def should_skip_path(path: Path) -> bool:
    name = path.name.lower()
    rel = str(path).replace("\\", "/").lower()
    if name in {"conversation.md", "project.md"}:
        return True
    if name.endswith(".env") or ".env." in name:
        return True
    if "/scripts/assets/" in rel or "/apps/" in rel:
        return True
    return False


def sanitize_wiki_markdown(text: str) -> str:
    out = text or ""
    out = _EMAIL_RE.sub("[email]", out)
    out = _PHONE_RE.sub("[phone]", out)
    out = _SNILS_RE.sub("[snils]", out)
    out = _UUID_RE.sub("[id]", out)
    out = _Y0_RE.sub("[oauth-token]", out)
    out = _CABINET_URL_RE.sub("[cabinet-url]", out)
    if len(out) > MAX_CONTENT_CHARS:
        out = out[: MAX_CONTENT_CHARS - 80] + "\n\n…\n\n_(обрезано для Wiki; канон в git)_\n"
    return out


def path_to_slug(path: Path, *, repo_root: Path) -> str:
    rel = path.resolve().relative_to(repo_root.resolve()).as_posix()
    if not rel.startswith("docs/"):
        raise ValueError(f"not under docs/: {rel}")
    without = rel[len("docs/") :]
    if without.lower().endswith(".md"):
        without = without[: -len(".md")]
    parts = []
    for p in without.split("/"):
        slug_part = re.sub(r"[^a-zA-Z0-9._-]+", "-", p).strip("-._").lower()
        if slug_part:
            parts.append(slug_part)
    return "/".join([WIKI_ROOT, *parts])


def title_from_markdown(text: str, fallback: str) -> str:
    for line in (text or "").splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()[:200] or fallback
    return fallback[:200]


def parent_slugs(slug: str) -> list[str]:
    parts = slug.strip("/").split("/")
    out: list[str] = []
    for i in range(1, len(parts)):
        out.append("/".join(parts[:i]))
    return out


def section_index_content(*, section: str, child_links: list[tuple[str, str]]) -> str:
    lines = [
        f"# SFRFR — {section}",
        "",
        "Канон в git. Без ПДн. Автосинк: `sfrfr wiki-docs-sync`.",
        "",
    ]
    for title, slug in sorted(child_links, key=lambda x: x[1]):
        lines.append(f"- [{title}](https://wiki.yandex.ru/{slug})")
    return "\n".join(lines) + "\n"


def build_staff_hub_content() -> str:
    return """# Инструкция сотруднику

Канон в git. В Wiki — удобный вход. **Без ПДн** в комментариях Tracker/Wiki.

## Быстрый старт

1. [Шпаргалка: новый лид](https://wiki.yandex.ru/sfrfr/ops/playbook-staff-new-lead-cheatsheet)
2. [CRM кабинета сотрудника](https://wiki.yandex.ru/sfrfr/ops/playbook-staff-cabinet-crm)
3. [Очередь на дашборде](https://wiki.yandex.ru/sfrfr/ops/staff-dashboard-work-queue)
4. [Роли и безопасные ops](https://wiki.yandex.ru/sfrfr/ops/staff-roles-safe-ops)
5. [Счета и оплаты](https://wiki.yandex.ru/sfrfr/ops/staff-finance-invoices)

## Воронка и SLA

- [SLA lead/qualify](https://wiki.yandex.ru/sfrfr/ops/playbook-funnel-lead-sla)
- [Clarity-разбор диалогов](https://wiki.yandex.ru/sfrfr/ops/playbook-funnel-clarity-dialog-review)
- [Реанимация дел](https://wiki.yandex.ru/sfrfr/ops/playbook-case-reactivation)
- [Ссылка на оплату клиенту](https://wiki.yandex.ru/sfrfr/ops/playbook-pay-link-to-client)

## Продажи / ясность (marketing)

- [Clarity funnel](https://wiki.yandex.ru/sfrfr/marketing-sales/playbook-sales-clarity-funnel)
- [Квалификация](https://wiki.yandex.ru/sfrfr/marketing-sales/playbook-sales-qualification)

## Позиция сервиса

Мы готовим документы, проект обращения и план — подаёте через СФР/Госуслуги вы сами.
Решение принимает СФР.
Не обещаем перерасчёт и сумму выплат. СНИЛС / ИЛС / сканы — только MAX и кабинет клиента.

## Разделы Wiki

- [ТЗ (specs)](https://wiki.yandex.ru/sfrfr/specs)
- [Ops](https://wiki.yandex.ru/sfrfr/ops)
- [История / опыт](https://wiki.yandex.ru/sfrfr/history)
- [Маркетинг и отчёты](https://wiki.yandex.ru/sfrfr/marketing-sales)
- [Индекс](https://wiki.yandex.ru/sfrfr)
"""


def collect_sync_pages(*, repo_root: Path) -> list[WikiPageSpec]:
    root = repo_root.resolve()
    found: dict[str, WikiPageSpec] = {}
    for pattern in SYNC_GLOBS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file() or path.suffix.lower() != ".md":
                continue
            if should_skip_path(path):
                continue
            try:
                slug = path_to_slug(path, repo_root=root)
            except ValueError:
                continue
            raw = path.read_text(encoding="utf-8", errors="replace")
            body = sanitize_wiki_markdown(raw)
            title = title_from_markdown(body, path.stem)
            footer = (
                f"\n\n---\n_Канон: `{path.relative_to(root).as_posix()}` · "
                f"синк Wiki · без ПДн._\n"
            )
            content = body.rstrip() + footer
            found[slug] = WikiPageSpec(
                slug=slug,
                title=title,
                content=content,
                source=path.relative_to(root).as_posix(),
            )

    # section hubs
    by_section: dict[str, list[tuple[str, str]]] = {
        "specs": [],
        "ops": [],
        "history": [],
        "marketing-sales": [],
    }
    for spec in found.values():
        parts = spec.slug.split("/")
        if len(parts) >= 3 and parts[1] in by_section:
            by_section[parts[1]].append((spec.title, spec.slug))

    hubs: list[WikiPageSpec] = []
    for section, links in by_section.items():
        if not links:
            continue
        hubs.append(
            WikiPageSpec(
                slug=f"{WIKI_ROOT}/{section}",
                title=f"SFRFR — {section}",
                content=section_index_content(section=section, child_links=links),
                source=f"(hub:{section})",
            )
        )

    hubs.append(
        WikiPageSpec(
            slug=STAFF_HUB_SLUG,
            title="Инструкция сотруднику",
            content=build_staff_hub_content(),
            source="(hub:staff)",
        )
    )

    # root index refresh
    root_links = [
        ("Инструкция сотруднику", STAFF_HUB_SLUG),
        ("ТЗ (specs)", f"{WIKI_ROOT}/specs"),
        ("Ops", f"{WIKI_ROOT}/ops"),
        ("История / опыт", f"{WIKI_ROOT}/history"),
        ("Маркетинг и отчёты", f"{WIKI_ROOT}/marketing-sales"),
    ]
    hubs.append(
        WikiPageSpec(
            slug=WIKI_ROOT,
            title="SFRFR — индекс ops",
            content=section_index_content(section="индекс", child_links=root_links)
            + "\nКанон в git. Сайт WP/кабинет сюда не зеркалируем.\n",
            source="(hub:root)",
        )
    )

    # order: shorter slug first (parents), then pages
    all_pages = list(found.values()) + hubs
    all_pages.sort(key=lambda p: (p.slug.count("/"), p.slug))
    return all_pages


def ensure_parent_chain(
    slug: str,
    *,
    ensure_page: Callable[[str, str, str], dict[str, Any]],
    known: set[str],
) -> None:
    for parent in parent_slugs(slug):
        if parent in known or parent == WIKI_ROOT:
            known.add(parent)
            continue
        title = parent.split("/")[-1]
        ensure_page(parent, f"SFRFR — {title}", f"# {title}\n\nРаздел Wiki. Канон в git.\n")
        known.add(parent)


def run_wiki_docs_sync(
    *,
    repo_root: Path | None = None,
    dry_run: bool = False,
    limit: int | None = None,
    sleep_s: float = 0.15,
    get_page_fn: Callable[[str], dict[str, Any] | None] | None = None,
    create_page_fn: Callable[..., dict[str, Any]] | None = None,
    update_page_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    root = (repo_root or Path.cwd()).resolve()
    pages = collect_sync_pages(repo_root=root)
    if limit is not None:
        pages = pages[: max(0, limit)]

    stats: dict[str, Any] = {
        "dry_run": dry_run,
        "total": len(pages),
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "errors": [],
    }
    if dry_run:
        stats["sample"] = [{"slug": p.slug, "source": p.source} for p in pages[:15]]
        stats["action"] = "would_sync"
        return stats

    get_page = get_page_fn or _default_get
    create_page = create_page_fn or _default_create
    update_page = update_page_fn or _default_update
    known: set[str] = {WIKI_ROOT}

    def ensure_page(slug: str, title: str, content: str) -> dict[str, Any]:
        existing = get_page(slug)
        if existing and existing.get("id") is not None:
            return update_page(
                page_id=existing["id"],
                title=title,
                content=content,
            )
        return create_page(slug=slug, title=title, content=content)

    for spec in pages:
        try:
            ensure_parent_chain(spec.slug, ensure_page=ensure_page, known=known)
            existing = get_page(spec.slug)
            if existing and existing.get("id") is not None:
                res = update_page(
                    page_id=existing["id"],
                    title=spec.title,
                    content=spec.content,
                )
                action = "updated"
            else:
                res = create_page(
                    slug=spec.slug,
                    title=spec.title,
                    content=spec.content,
                )
                action = "created"
            if res.get("ok"):
                if action == "created":
                    stats["created"] += 1
                else:
                    stats["updated"] += 1
                known.add(spec.slug)
            else:
                stats["failed"] += 1
                stats["errors"].append(
                    {"slug": spec.slug, "error": res.get("error") or res.get("status_code")}
                )
        except Exception as exc:  # noqa: BLE001
            stats["failed"] += 1
            stats["errors"].append({"slug": spec.slug, "error": type(exc).__name__})
            logger.warning("wiki_sync_failed slug=%s err=%s", spec.slug, type(exc).__name__)
        if sleep_s > 0:
            time.sleep(sleep_s)
    return stats


def _default_get(slug: str) -> dict[str, Any] | None:
    from sfrfr.integrations.yandex_wiki import get_page_by_slug

    return get_page_by_slug(slug)


def _default_create(**kwargs: Any) -> dict[str, Any]:
    from sfrfr.integrations.yandex_wiki import create_page

    return create_page(**kwargs)


def _default_update(**kwargs: Any) -> dict[str, Any]:
    from sfrfr.integrations.yandex_wiki import update_page

    return update_page(**kwargs)
