"""Приёмка ТЗ-07: этапы MVP закрыты скелетом без утечки ПДн вне API/кабинетов."""

from __future__ import annotations

import json
from pathlib import Path

from sfrfr.ai.schemas.agents import DraftResult
from sfrfr.api import create_app
from sfrfr.core.case_store import get_case_store, reset_case_store
from sfrfr.core.config import get_settings
from sfrfr.core.success_fee import calc_success_fee
from sfrfr.integrations.max.attachments import extract_downloadable_files
from sfrfr.integrations.max.handler import handle_max_update
from sfrfr.security.integrations import SIGNED_URL_TTL_SECONDS

REPO = Path(__file__).resolve().parents[2]


class _SilentBot:
    def __init__(self) -> None:
        self.sent: list[tuple[object, str]] = []

    @property
    def available(self) -> bool:
        return True

    def send_message(self, *, text: str, user_id=None, chat_id=None, attachments=None):  # noqa: ANN001
        self.sent.append((user_id or chat_id, text))
        return {"ok": True}


def test_stage1_wp_cta_points_to_application_and_cabinet() -> None:
    seed = (REPO / "scripts/wp_seed_site_tz02.sh").read_text(encoding="utf-8")
    assert "/#kak-prohodit" in seed
    assert "Статьи" in seed
    assert "MAX_CHAT_URL" in seed or "MAX_BTN_URL" in seed
    home = (REPO / "scripts/assets/sfrfr-home.html").read_text(encoding="utf-8")
    assert 'id="zayavka"' in home  # форма заявки остаётся
    assert 'id="kak-rabotat"' in home
    # ТЗ-20/21: первичный CTA — личный чат MAX, не кабинет/канал; нейтральный текст
    assert "Уточнить ситуацию в MAX" in home
    assert "Начать проверку в MAX" not in home
    assert "Позвонить" in home
    assert "tel:+79091950408" in home
    assert "sfrfr-hero__identity" in home
    assert "8905066468" in home
    assert "{{MAX_BTN_URL}}" in home
    assert "cabinet.proverkastaza.ru/?channel=max" not in home
    assert "Открыть кабинет на сайте" not in home
    assert "Сканы — только в MAX или кабинете" not in home
    assert 'id="o-servise"' in home
    assert home.index('id="o-servise"') < home.index('id="tarify"')
    # ТЗ-22: опыт + заглушка наград (фото — после подготовки)
    assert "Опыт работы в социальной сфере — 8 лет." in home
    assert "Награды и профессиональные материалы" in home
    assert "будут добавлены после проверки и подготовки к публикации" in home
    assert 'id="sfrfr-awards-data"' in home
    assert (REPO / "scripts/assets/sfrfr-awards.js").exists()
    search_mu = (REPO / "scripts/wp-mu-plugins/sfrfr-site-search.php").read_text(encoding="utf-8")
    assert "sfrfr-site-search" in search_mu
    assert 'name="s"' in search_mu
    assert "Поиск по сайту" in search_mu
    assert "sfrfr_render_search_feed" in search_mu
    assert "sfrfr-search-hit" in search_mu
    assert "упоминаний" in search_mu
    assert "sfrfr_search_per_page" in search_mu
    assert "sfrfr-search-item--right" in search_mu
    assert "Пример расчёта вознаграждения" in home
    assert 'id="komu"' in home
    assert "sfrfr-sticky-cta" in home
    assert 'id="stati"' in home  # 3 карточки блога (§13.3)
    assert "Полезные статьи" in home
    form = (REPO / "scripts/wp_ensure_lead_form.php").read_text(encoding="utf-8")
    assert "Электронная почта" in form
    assert "Телефон" in form
    assert "хотя бы" in form.lower() or "почту или телефон" in form.lower()
    assert "'type' => 'file'" not in form
    assert "Личный кабинет на сайте" in form
    assert "channel=max" not in form
    assert "mode=register" in form
    assert "только в MAX или кабинете" not in form
    assert "?startapp" not in form


def test_tz11_blog_mvp_assets() -> None:
    """ТЗ-11: сид статей (включая контент с главной), дисклеймер, CTA."""
    assert (REPO / "scripts/wp_seed_blog_tz11.sh").exists()
    assert (REPO / "scripts/wp_seed_blog_tz11.php").exists()
    php = (REPO / "scripts/wp_seed_blog_tz11.php").read_text(encoding="utf-8")
    assert "kak-proverit-stazh-v-vypiske-ils" in php
    assert "kak-sverit-trudovuyu-knizhku-i-ils" in php
    assert "chto-delat-esli-period-raboty-ne-uchten" in php
    assert "arhivnaya-spravka-dlya-sfr-zachem-i-kuda" in php
    assert "kakie-dokumenty-sobrat-do-obrashcheniya-v-sfr" in php
    assert "kak-podat-zayavlenie-cherez-gosuslugi-ili-mfc" in php
    assert "otkaz-sfr-chto-proverit-v-dokumentah" in php
    assert "pensiya-po-invalidnosti-i-stazh-na-chto-smotret" in php
    assert "kak-pomoch-rodstvenniku-proverit-stazh" in php
    assert "chem-otlichaetsya-diagnostika-ot-soprovozhdeniya" in php
    assert "pochemu-reshenie-prinimaet-tolko-sfr" in php
    assert "chek-list-pered-zapisju-v-mfc" in php
    assert "rodstvenniki" in php
    assert "default_comment_status" in php
    assert "tipichnye-situacii-proverki-stazha" in php
    assert "chto-vy-poluchite-posle-proverki-stazha" in php
    assert "kak-rabotat-v-max-i-lichnom-kabinete" in php
    assert "chastye-voprosy-o-proverke-stazha" in php
    assert "Не являемся СФР" in php
    assert "blog/rubrika" in php
    for name in (
        "01-ils-stazh.html",
        "02-trudovaya-ils.html",
        "03-period-ne-uchten.html",
        "04-arhivnaya-spravka.html",
        "05-tipichnye-situacii.html",
        "06-dlya-rodstvennikov.html",
        "07-chto-vy-poluchite.html",
        "08-max-i-kabinet.html",
        "09-faq-rasshirennyy.html",
        "10-dokumenty-do-sfr.html",
        "11-podacha-gosuslugi-mfc.html",
        "12-otkaz-sfr.html",
        "13-invalidnost-i-stazh.html",
        "14-diagnostika-vs-soprovozhdenie.html",
        "15-pochemu-reshenie-sfr.html",
        "16-chek-list-mfc.html",
    ):
        body = (REPO / "scripts/assets/blog" / name).read_text(encoding="utf-8")
        assert "<h1>" in body
        assert "гарантируем перерасчёт" not in body.lower()
        assert "официальный сервис" not in body.lower()
        assert "100%" not in body
        assert "мы гарантируем" not in body.lower()
    home = (REPO / "scripts/assets/sfrfr-home.html").read_text(encoding="utf-8")
    assert 'id="faq"' in home
    assert 'id="stati"' in home
    assert "/blog/tipichnye-situacii-proverki-stazha/" in home
    assert "/blog/chastye-voprosy-o-proverke-stazha/" in home
    assert "/blog/kak-proverit-stazh-v-vypiske-ils/" in home
    assert (REPO / "docs/ops-blog-editor.md").exists()
    mu = (REPO / "scripts/wp-mu-plugins/sfrfr-blog-ui.php").read_text(encoding="utf-8")
    assert "'rodstvenniki'" in mu
    assert "dlya-rodstvennikov" not in mu
    assert "Статьи о проверке стажа и ИЛС</h1>" in mu
    seo = (REPO / "scripts/wp-mu-plugins/sfrfr-seo-meta.php").read_text(encoding="utf-8")
    assert 'name=\\"description\\"' in seo
    assert 'rel=\\"canonical\\"' in seo
    assert "application/ld+json" in seo
    assert "Organization" in seo
    assert "GovernmentOrganization" not in seo
    assert "preg_replace('/^\\s*(?:<!--.*?-->\\s*)*<h1" in seo
    deploy = (REPO / "scripts/wp_deploy_blog_ui.sh").read_text(encoding="utf-8")
    assert "sfrfr-seo-meta.php" in deploy
    assert "sfrfr-seo-redirects.php" in deploy
    assert "cache flush" in deploy
    assert (REPO / "scripts/wp-mu-plugins/sfrfr-seo-redirects.php").exists()
    assert (REPO / "scripts/assets/blog/21-zakazat-vypisku-ils.html").exists()
    assert "kak-zakazat-vypisku-ils" in php
    miniapp = (REPO / "web/max-miniapp/index.html").read_text(encoding="utf-8")
    assert 'name="robots" content="noindex,nofollow,noarchive"' in miniapp


def test_blog_situations_from_deepseek() -> None:
    """Обезличенные ситуации (1 на клиента) + аналитика каждые 5."""
    manifest = REPO / "scripts/assets/blog/situations/manifest.json"
    assert manifest.exists()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(data["situations"]) == 25
    assert len(data["analytics"]) == 5
    assert len(data["analytics"]) * 5 == len(data["situations"])
    for s in data["situations"]:
        blob = json.dumps(s, ensure_ascii=False).lower()
        assert "гарантируем" not in blob
        assert "мирошниченко" not in blob
        assert "наталия" not in blob
    index = REPO / "scripts/assets/blog/situations/html/index.json"
    assert index.exists()
    items = json.loads(index.read_text(encoding="utf-8"))
    assert len(items) == 30
    assert (REPO / "scripts/wp_seed_blog_situations.sh").exists()
    assert (REPO / "scripts/generate_blog_situations.py").exists()


def test_stage4_success_fee_formula() -> None:
    fee = calc_success_fee(lump_sum_rub=100_000, monthly_increase_rub=2_000)
    assert fee["sf_lump"] == 10_000
    assert fee["sf_month"] == 3_000  # 50% * 2000 * 3


def test_stage3_signed_url_short_ttl() -> None:
    assert SIGNED_URL_TTL_SECONDS <= 120


def test_stage6_sheets_and_amocrm_modules_exist() -> None:
    assert (REPO / "src/sfrfr/integrations/sheets/__init__.py").exists()
    assert (REPO / "src/sfrfr/integrations/amocrm/__init__.py").exists()
    assert (REPO / "src/sfrfr/integrations/payments/__init__.py").exists()
    assert not (REPO / "src/sfrfr/integrations/taganay/__init__.py").exists()


def test_public_leads_route_registered() -> None:
    app = create_app()
    paths = set(app.openapi()["paths"])
    assert "/api/public/leads" in paths
    assert "/api/portal/cases/{case_id}/orders/{order_id}/pay" in paths
    assert "/api/integrations/payments/yookassa/webhook" in paths


def test_max_docs_and_draft_commands(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path / "uploads"))
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    get_settings.cache_clear()
    reset_case_store(tmp_path / "cases.json")
    from sfrfr.integrations.max.intake import reset_intake_store

    reset_intake_store(tmp_path / "max_intake.json")
    bot = _SilentBot()

    handle_max_update(
        {
            "message": {
                "sender": {"user_id": 101},
                "recipient": {"chat_id": 1, "chat_type": "dialog"},
                "body": {"text": "/start"},
            }
        },
        bot=bot,
    )
    for payload in (
        "intake:goal:check_experience",
        "intake:ils:yes",
        "intake:emp:partial",
        "intake:device:web",
    ):
        done = handle_max_update(
            {
                "callback": {
                    "user": {"user_id": 101},
                    "chat_id": 1,
                    "payload": payload,
                }
            },
            bot=bot,
        )
    assert done.case_id
    assert done.action == "max_intake_completed"
    assert any("защищённо" in t.lower() for _, t in bot.sent)

    docs = handle_max_update(
        {
            "message": {
                "sender": {"user_id": 101},
                "recipient": {"chat_id": 1},
                "body": {"text": "/docs"},
            }
        },
        bot=bot,
    )
    assert docs.action == "docs_request"
    assert any("ИЛС" in t for _, t in bot.sent)

    store = get_case_store()
    with store._lock:  # noqa: SLF001
        store._load()  # noqa: SLF001
        record = store._cases[done.case_id]  # noqa: SLF001
        record.ctx.draft = DraftResult(
            title="Заявление",
            body="Прошу перерасчёт пенсии по стажу.",
            findings_used=[],
        )
        store._save()  # noqa: SLF001

    draft = handle_max_update(
        {
            "message": {
                "sender": {"user_id": 101},
                "recipient": {"chat_id": 1},
                "body": {"text": "/draft"},
            }
        },
        bot=bot,
    )
    assert draft.action == "draft"
    assert draft.ok is True
    assert any("Прошу перерасчёт" in t for _, t in bot.sent)
    get_settings.cache_clear()


def test_max_attachment_url_extraction() -> None:
    files = extract_downloadable_files(
        {
            "message": {
                "body": {
                    "attachments": [
                        {
                            "type": "file",
                            "payload": {
                                "url": "https://cdn.example/f.pdf",
                                "file_name": "ils.pdf",
                            },
                        }
                    ]
                }
            }
        }
    )
    assert files == [("ils.pdf", "https://cdn.example/f.pdf")]


def test_pdn_not_in_frontend_env() -> None:
    for rel in ("apps/cabinet/.env.example", "apps/admin/.env.example"):
        text = (REPO / rel).read_text(encoding="utf-8")
        for line in text.splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            key = raw.split("=", 1)[0].strip().upper()
            assert "SERVICE_ROLE" not in key
            assert not key.startswith("NEXT_PUBLIC_") or "SERVICE" not in key
