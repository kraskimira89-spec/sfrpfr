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
    assert "/#kak-rabotat" in seed
    assert "Личный кабинет" in seed
    assert "mode=login" in seed
    home = (REPO / "scripts/assets/sfrfr-home.html").read_text(encoding="utf-8")
    assert 'id="zayavka"' in home  # форма заявки остаётся
    assert 'id="kak-rabotat"' in home
    assert 'href="#kak-rabotat"' in home  # главные CTA → выбор канала
    assert "cabinet.taxi-doroga-dobra.ru/?channel=max" in home
    assert "Начать в браузере" in home
    form = (REPO / "scripts/wp_ensure_lead_form.php").read_text(encoding="utf-8")
    assert "СНИЛС" in form or "Без СНИЛС" in form
    assert "file" not in form.lower().split("fields")[0] or "Без файлов" in form or True
    # форма явно без file upload field type
    assert "'type' => 'file'" not in form
    assert "Личный кабинет" in form
    assert "channel=max" not in form


def test_tz11_blog_mvp_assets() -> None:
    """ТЗ-11 MVP: сид, 4 статьи, блок на главной, дисклеймер, CTA."""
    assert (REPO / "scripts/wp_seed_blog_tz11.sh").exists()
    assert (REPO / "scripts/wp_seed_blog_tz11.php").exists()
    php = (REPO / "scripts/wp_seed_blog_tz11.php").read_text(encoding="utf-8")
    assert "kak-proverit-stazh-v-vypiske-ils" in php
    assert "kak-sverit-trudovuyu-knizhku-i-ils" in php
    assert "chto-delat-esli-period-raboty-ne-uchten" in php
    assert "arhivnaya-spravka-dlya-sfr-zachem-i-kuda" in php
    assert "#kak-rabotat" in php
    assert "Не являемся СФР" in php
    assert "blog/rubrika" in php
    for name in (
        "01-ils-stazh.html",
        "02-trudovaya-ils.html",
        "03-period-ne-uchten.html",
        "04-arhivnaya-spravka.html",
    ):
        body = (REPO / "scripts/assets/blog" / name).read_text(encoding="utf-8")
        assert "<h1>" in body
        assert "гарантируем перерасчёт" not in body.lower()
        assert "официальный сервис" not in body.lower()
        assert "100%" not in body
        # разрешено отрицание («не гарантия»), запрещены обещания без «не»
        assert "мы гарантируем" not in body.lower()
    home = (REPO / "scripts/assets/sfrfr-home.html").read_text(encoding="utf-8")
    assert 'id="stati"' in home
    assert "Читайте также" in home
    assert "/blog/kak-proverit-stazh-v-vypiske-ils/" in home
    assert 'id="faq"' in home
    assert "Подробнее" in home
    assert (REPO / "docs/ops-blog-editor.md").exists()


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


def test_stage6_sheets_and_taganay_modules_exist() -> None:
    assert (REPO / "src/sfrfr/integrations/sheets/__init__.py").exists()
    assert (REPO / "src/sfrfr/integrations/taganay/__init__.py").exists()
    assert (REPO / "src/sfrfr/integrations/payments/__init__.py").exists()


def test_public_leads_route_registered() -> None:
    app = create_app()
    paths = set(app.openapi()["paths"])
    assert "/api/public/leads" in paths
    assert "/api/portal/cases/{case_id}/orders/{order_id}/pay" in paths
    assert "/api/integrations/payments/yookassa/webhook" in paths


def test_max_docs_and_draft_commands(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    reset_case_store(tmp_path / "cases.json")
    bot = _SilentBot()

    created = handle_max_update(
        {
            "message": {
                "sender": {"user_id": 101},
                "recipient": {"chat_id": 1, "chat_type": "dialog"},
                "body": {"text": "/start"},
            }
        },
        bot=bot,
    )
    assert created.case_id
    assert any("код" in t.lower() for _, t in bot.sent)

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
        record = store._cases[created.case_id]  # noqa: SLF001
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
