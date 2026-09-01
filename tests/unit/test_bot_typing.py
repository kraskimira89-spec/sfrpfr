"""Копирайт и ограничения индикатора «бот печатает»."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TYPING = (ROOT / "shared" / "bot-typing.ts").read_text(encoding="utf-8")


def test_typing_ignores_document_events_and_has_short_window() -> None:
    assert "[Документ]" in TYPING
    assert "BOT_TYPING_MS = 8_000" in TYPING
    assert "BOT_TYPING_TIMEOUT_MS = 50_000" in TYPING
    assert "lastClientAwaitAgeMs" in TYPING
