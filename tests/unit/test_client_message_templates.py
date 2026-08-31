"""Регрессия: клиентские шаблоны — канон MAX + кабинет, без «только в ЛК»."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

BANNED = (
    "только в личном кабинете",
    "не в этот чат",
    "Сканы — только",
    "загружаются только в защищённом",
    "загружаются только в защищенном",
    "документы только в кабинете",
    "принимаются только в защищённом",
    "принимаются только в защищенном",
    "передаются только через защищённый",
    "возможна только через защищённый",
    "файлы — только в защищённый",
    "документы — только в кабинете",
)

SKIP_IF_CONTAINS = (
    "запрещённ",
    "запрещенн",
    "do not use",
)

CLIENT_TEMPLATE_PATHS = (
    REPO / "apps/admin/src/lib/case-funnel.ts",
    REPO / "src/sfrfr/api/routes/public_leads.py",
    REPO / "src/sfrfr/integrations/yandex_workspace/mail.py",
    REPO / "src/sfrfr/integrations/max/llm_chat.py",
    REPO / "src/sfrfr/integrations/max/handler.py",
    REPO / "scripts/assets/sfrfr-home.html",
    REPO / "scripts/assets/copy/ils-self-check-checklist.md",
)

DOCS_AND_COPY_GLOBS = (
    "docs/marketing-sales/**/*.md",
    "docs/VK/**/*.md",
    "docs/AMO/**/*.md",
    "docs/specs/2*.md",
    "docs/strategy/**/*.md",
    "scripts/assets/blog/*.html",
    "scripts/assets/trust/*.html",
    "scripts/assets/copy/*.md",
    "scripts/assets/max-channel/*.json",
)


def _iter_doc_copy_paths() -> list[Path]:
    paths: list[Path] = []
    for pattern in DOCS_AND_COPY_GLOBS:
        paths.extend(REPO.glob(pattern))
    return sorted(set(paths))


def _assert_no_banned(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    lower = text.lower()
    if any(skip in lower for skip in SKIP_IF_CONTAINS) and path.name.startswith(
        ("21-trust", "docs-channel-canon")
    ):
        return
    for phrase in BANNED:
        if phrase in lower:
            if path.name == "21-trust-first-contact.md" and "запрещён" in lower:
                continue
            assert False, f"{path.relative_to(REPO)}: запрещённая формулировка «{phrase}»"


def test_client_templates_no_cabinet_only_wording() -> None:
    for path in CLIENT_TEMPLATE_PATHS:
        _assert_no_banned(path)


def test_docs_and_copy_no_cabinet_only_wording() -> None:
    for path in _iter_doc_copy_paths():
        _assert_no_banned(path)


def test_admin_doc_request_mentions_max_chat() -> None:
    ts = (REPO / "apps/admin/src/lib/case-funnel.ts").read_text(encoding="utf-8")
    assert "в этот чат" in ts
    assert "PDF/JPG/PNG" in ts


def test_mail_request_docs_mentions_max() -> None:
    mail = (REPO / "src/sfrfr/integrations/yandex_workspace/mail.py").read_text(
        encoding="utf-8"
    )
    assert "чат MAX" in mail


def test_docs_channel_canon_file_exists() -> None:
    canon = REPO / "scripts/assets/copy/docs-channel-canon.md"
    assert canon.is_file()
    body = canon.read_text(encoding="utf-8")
    assert "личный чат MAX" in body
    assert "cabinet.proverkastaza.ru" in body
