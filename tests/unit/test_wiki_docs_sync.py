"""Синхронизация docs → Яндекс Wiki (без сайта, без ПДн)."""

from __future__ import annotations

from pathlib import Path

from sfrfr.services.wiki_docs_sync import (
    STAFF_HUB_SLUG,
    build_staff_hub_content,
    collect_sync_pages,
    path_to_slug,
    sanitize_wiki_markdown,
    should_skip_path,
)


def test_path_to_slug_specs_and_nested() -> None:
    root = Path("/repo")
    assert (
        path_to_slug(root / "docs/specs/01-architecture.md", repo_root=root)
        == "sfrfr/specs/01-architecture"
    )
    assert (
        path_to_slug(
            root / "docs/marketing-sales/reports/weekly-template.md",
            repo_root=root,
        )
        == "sfrfr/marketing-sales/reports/weekly-template"
    )


def test_sanitize_strips_email_phone_snils() -> None:
    raw = "Пиши на a@b.ru или +7 900 111-22-33, СНИЛС 123-456-789 00"
    out = sanitize_wiki_markdown(raw)
    assert "a@b.ru" not in out
    assert "+7 900" not in out
    assert "123-456-789" not in out
    assert "[email]" in out


def test_should_skip_conversation_and_secrets() -> None:
    assert should_skip_path(Path("docs/history/conversation.md"))
    assert should_skip_path(Path("docs/history/project.md"))
    assert not should_skip_path(Path("docs/ops/playbook-staff-cabinet-crm.md"))


def test_collect_includes_scopes(tmp_path: Path) -> None:
    (tmp_path / "docs/specs").mkdir(parents=True)
    (tmp_path / "docs/ops").mkdir(parents=True)
    (tmp_path / "docs/history").mkdir(parents=True)
    (tmp_path / "docs/marketing-sales/reports").mkdir(parents=True)
    (tmp_path / "docs/specs/01.md").write_text("# A\n", encoding="utf-8")
    (tmp_path / "docs/ops/playbook.md").write_text("# B\n", encoding="utf-8")
    (tmp_path / "docs/history/2026-01-01-x.md").write_text("# C\n", encoding="utf-8")
    (tmp_path / "docs/history/conversation.md").write_text("pii\n", encoding="utf-8")
    (tmp_path / "docs/marketing-sales/README.md").write_text("# M\n", encoding="utf-8")
    pages = collect_sync_pages(repo_root=tmp_path)
    slugs = {p.slug for p in pages}
    assert "sfrfr/specs/01" in slugs
    assert "sfrfr/ops/playbook" in slugs
    assert "sfrfr/history/2026-01-01-x" in slugs
    assert "sfrfr/marketing-sales/readme" in slugs or "sfrfr/marketing-sales/README" in slugs
    assert "sfrfr/history/conversation" not in slugs
    # parents before children
    assert slugs  # non-empty


def test_staff_hub_lists_key_links() -> None:
    text = build_staff_hub_content()
    assert STAFF_HUB_SLUG == "sfrfr/staff"
    assert "playbook-staff-cabinet-crm" in text
    assert "playbook-staff-new-lead-cheatsheet" in text
    assert "ПДн" in text or "без ПДн" in text.lower() or "СНИЛС" in text
