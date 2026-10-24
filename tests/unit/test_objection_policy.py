"""SFRFR-110: возражения ≠ претензии; без давления и повторного offer."""

from __future__ import annotations

import pytest

from sfrfr.services.objection_policy import (
    BANNED_OBJECTION_REPLY_MARKERS,
    PAYMENT_REFUSAL_IS_NOT,
    ClientSignalKind,
    classify_client_signal,
    is_claim_or_stop,
    may_reoffer_after_signal,
    reply_has_banned_objection_pressure,
)


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Дорого для меня", ClientSignalKind.PRICE_OBJECTION),
        ("Нет денег сейчас", ClientSignalKind.NO_MONEY),
        ("Вы гарантируете перерасчёт?", ClientSignalKind.GUARANTEE_ASK),
        ("Я могу сам обратиться в СФР", ClientSignalKind.SELF_SERVICE),
        ("СФР уже всё проверил", ClientSignalKind.SFR_ALREADY_CHECKED),
        ("Мне уже отказали", ClientSignalKind.SFR_REFUSED),
        ("Я вам не доверяю", ClientSignalKind.TRUST),
        ("Боюсь отправлять документы", ClientSignalKind.FEAR_DOCS),
        ("У меня нет документов", ClientSignalKind.NO_DOCS),
        ("Я не умею загружать", ClientSignalKind.CANT_UPLOAD),
        ("Я уже всё отправлял", ClientSignalKind.ALREADY_SENT),
        ("Я подумаю", ClientSignalKind.THINKING),
        ("Мне нужно посоветоваться с женой", ClientSignalKind.CONSULT_OTHERS),
        ("Не хочу, не надо", ClientSignalKind.HARD_REFUSE),
        ("Не пишите мне", ClientSignalKind.STOP_MESSAGES),
        ("СТОП", ClientSignalKind.STOP_MESSAGES),
        ("Верните деньги", ClientSignalKind.CLAIM),
        ("Я оплатил а результата нет", ClientSignalKind.CLAIM),
        ("Позовите специалиста", ClientSignalKind.ASK_SPECIALIST),
        ("Сколько стоит диагностика?", ClientSignalKind.CONDITIONS_QUESTION),
    ],
)
def test_classify_objection_categories(text: str, kind: ClientSignalKind) -> None:
    assert classify_client_signal(text) == kind


def test_claim_not_treated_as_price_cycle() -> None:
    kind = classify_client_signal("Списали дважды, верните деньги")
    assert kind == ClientSignalKind.CLAIM
    assert is_claim_or_stop(kind)
    assert may_reoffer_after_signal(kind) is False


def test_hard_refuse_and_pause_block_reoffer() -> None:
    assert may_reoffer_after_signal(ClientSignalKind.HARD_REFUSE) is False
    assert may_reoffer_after_signal(ClientSignalKind.THINKING) is False
    assert may_reoffer_after_signal(ClientSignalKind.NO_MONEY) is False
    assert may_reoffer_after_signal(ClientSignalKind.PRICE_OBJECTION) is True


def test_banned_pressure_phrases_detected() -> None:
    assert reply_has_banned_objection_pressure(
        "Успейте сегодня, окупится за счёт прибавки"
    )
    assert not reply_has_banned_objection_pressure(
        "Понимаю. Оформлять платную услугу сейчас не обязательно."
    )
    assert "гарантируем перерасчёт" in BANNED_OBJECTION_REPLY_MARKERS


def test_payment_refusal_is_not_data_delete() -> None:
    assert "data_delete" in PAYMENT_REFUSAL_IS_NOT
    assert "all_messages_stop" in PAYMENT_REFUSAL_IS_NOT


def test_existing_offer_skip_and_detail_no_align_with_refuse() -> None:
    """Не обходим evidence-гейты: отказ кнопкой ≠ новый продажный цикл."""
    from sfrfr.integrations.max.diag_choice import DETAIL_DECLINED_TEXT
    from sfrfr.services.max_bot_invoice import resolve_offer_cta

    assert resolve_offer_cta("подумаю") == "offer:docs_skip"
    assert resolve_offer_cta("сам по плану") == "offer:docs_skip"
    # Soft-ask «нет»: принять паузу, не новый продажный питч.
    assert "хорошо" in DETAIL_DECLINED_TEXT.lower()
    assert "гарант" not in DETAIL_DECLINED_TEXT.lower()
    assert may_reoffer_after_signal(ClientSignalKind.THINKING) is False
