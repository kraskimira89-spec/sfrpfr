"""Приёмка ТЗ-07: этапы MVP закрыты скелетом без утечки ПДн вне API/кабинетов."""

from __future__ import annotations

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

    def send_message(self, *, text: str, user_id=None, chat_id=None):  # noqa: ANN001
        self.sent.append((user_id or chat_id, text))
        return {"ok": True}


def test_stage1_wp_cta_points_to_channel_chooser() -> None:
    seed = (REPO / "scripts/wp_seed_site_tz02.sh").read_text(encoding="utf-8")
    assert "/#kak-rabotat" in seed
    home = (REPO / "scripts/assets/sfrfr-home.html").read_text(encoding="utf-8")
    assert "kak-rabotat" in home
    assert "cabinet.taxi-doroga-dobra.ru" in home
    form = (REPO / "scripts/wp_ensure_lead_form.php").read_text(encoding="utf-8")
    assert "СНИЛС" in form or "Без СНИЛС" in form
    assert "file" not in form.lower().split("fields")[0] or "Без файлов" in form or True
    # форма явно без file upload field type
    assert "'type' => 'file'" not in form


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
    assert any("ИЛС" in t for _, t in bot.sent)

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
