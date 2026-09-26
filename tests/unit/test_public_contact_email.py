"""Единый публичный e-mail оператора: сайт (юр. тексты, контакты) и бот MAX."""

from pathlib import Path

from sfrfr.services.client_pdn_consent import CONSENT_GATE_TEXT

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_EMAIL = "proverkastaza@yandex.ru"
OLD_EMAILS = ("info@proverkastaza.ru", "prismotr89@yandex.ru")
PUBLIC_FILES = (
    "scripts/assets/sfrfr-consent.html",
    "scripts/assets/sfrfr-privacy.html",
    "scripts/assets/sfrfr-oferta.html",
    "scripts/assets/sfrfr-cookies.html",
    "scripts/assets/trust/kontakty.html",
    "scripts/assets/trust/expert-lopakova.html",
    "scripts/assets/trust/partneram.html",
    "docs/contracts/pdn-consent.md",
    "docs/contracts/pdn-policy.md",
    "docs/contracts/offer-draft.md",
    "docs/contracts/browser-storage-policy.md",
    "scripts/wp-mu-plugins/sfrfr-site-footer.php",
    "scripts/wp-mu-plugins/sfrfr-seo-meta.php",
)


def test_bot_consent_uses_public_email() -> None:
    assert PUBLIC_EMAIL in CONSENT_GATE_TEXT
    for old in OLD_EMAILS:
        assert old not in CONSENT_GATE_TEXT


def test_public_site_texts_use_public_email() -> None:
    for rel in PUBLIC_FILES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert PUBLIC_EMAIL in text, rel
        for old in OLD_EMAILS:
            assert old not in text, f"{rel}: {old}"
