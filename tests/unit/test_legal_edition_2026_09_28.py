"""Юрредакция 2026-09-28: отдельное согласие на ПДн (ч. 1 ст. 9 152-ФЗ) и хостинг."""

from __future__ import annotations

from pathlib import Path

from sfrfr.core.copy import PAYMENT_LEGAL_ACCEPTANCE, PAYMENT_LEGAL_ACCEPTANCE_WITH_LINKS
from sfrfr.db.case_repository import CURRENT_CONSENT_VERSION
from sfrfr.services.case_chat_bot import __file__ as case_chat_bot_file
from sfrfr.services.public_tariffs import FINANCE_DISCLAIMER

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "scripts" / "assets"


def test_consent_version_is_new_edition() -> None:
    assert CURRENT_CONSENT_VERSION == "pdn-consent-2026-09-28"


def test_payment_text_does_not_bundle_pdn_consent() -> None:
    for text in (
        PAYMENT_LEGAL_ACCEPTANCE,
        PAYMENT_LEGAL_ACCEPTANCE_WITH_LINKS,
        FINANCE_DISCLAIMER,
        Path(case_chat_bot_file).read_text(encoding="utf-8"),
    ):
        assert "означает согласие с обработкой" not in text
    assert "оферт" in PAYMENT_LEGAL_ACCEPTANCE
    assert "отдельно" in PAYMENT_LEGAL_ACCEPTANCE


def test_cabinet_payment_hints_do_not_bundle_pdn_consent() -> None:
    for name in ("client-cabinet.tsx", "case-work-map.tsx"):
        src = (ROOT / "apps" / "cabinet" / "src" / "components" / name).read_text(encoding="utf-8")
        assert "означает согласие с обработкой" not in src, name


def test_consent_version_synced_in_clients() -> None:
    for rel in (
        "apps/cabinet/src/components/client-cabinet.tsx",
        "web/max-miniapp/app.js",
        "src/sfrfr/api/schemas/portal.py",
    ):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert CURRENT_CONSENT_VERSION in src, rel
        assert "pdn-consent-2026-09-09" not in src, rel


def test_legal_pages_new_editions_and_hosting() -> None:
    privacy = (ASSETS / "sfrfr-privacy.html").read_text(encoding="utf-8")
    consent = (ASSETS / "sfrfr-consent.html").read_text(encoding="utf-8")
    assert "pdn-policy-2026-09-28" in privacy
    assert "pdn-consent-2026-09-28" in consent
    for html in (privacy, consent):
        assert "7733568767" in html  # ООО «РЕГ.РУ» — хостинг приложения
        assert "Postbox" in html
        assert "«Начать»" in html
