"""Регрессия: клиентские шаблоны — канон MAX + кабинет, без «только в ЛК»."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

BANNED = (
    "только в личном кабинете",
    "не в этот чат",
    "не в MAX",
    "Сканы — только",
    "загружаются только в защищённом",
    "загружаются только в защищенном",
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


def test_client_templates_no_cabinet_only_wording() -> None:
    for path in CLIENT_TEMPLATE_PATHS:
        text = path.read_text(encoding="utf-8").lower()
        for phrase in BANNED:
            assert phrase not in text, f"{path.name}: запрещённая формулировка «{phrase}»"


def test_admin_doc_request_mentions_max_chat() -> None:
    ts = (REPO / "apps/admin/src/lib/case-funnel.ts").read_text(encoding="utf-8")
    assert "в этот чат" in ts
    assert "PDF/JPG/PNG" in ts


def test_mail_request_docs_mentions_max() -> None:
    mail = (REPO / "src/sfrfr/integrations/yandex_workspace/mail.py").read_text(
        encoding="utf-8"
    )
    assert "чат MAX" in mail
