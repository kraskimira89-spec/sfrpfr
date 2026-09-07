"""Throttle позиции сервиса 1/10 и согласие ПДн один раз."""

from __future__ import annotations

from sfrfr.services.position_throttle import (
    POSITION_EVERY_N,
    apply_position_policy,
    should_include_position,
    strip_position_phrases,
)


def test_should_include_position_every_tenth() -> None:
    assert should_include_position(outbound_count=0) is True  # 1-е
    assert should_include_position(outbound_count=1) is False
    assert should_include_position(outbound_count=9) is False
    assert should_include_position(outbound_count=10) is True  # 11-е
    assert POSITION_EVERY_N == 10


def test_strip_and_apply_policy() -> None:
    raw = (
        "Загрузите ИЛС в кабинете. "
        "Мы готовим документы и план — подаёте через СФР вы сами. Решение принимает СФР."
    )
    cleaned = strip_position_phrases(raw)
    assert "подаёте через" not in cleaned.lower()
    assert "ИЛС" in cleaned
    with_pos = apply_position_policy("Загрузите ИЛС.", allow=True)
    assert "Решение принимает СФР" in with_pos
    without = apply_position_policy("Загрузите ИЛС.", allow=False)
    assert "Решение принимает СФР" not in without


def test_client_has_pdn_consent() -> None:
    from sfrfr.services.client_pdn_consent import client_has_pdn_consent

    assert client_has_pdn_consent(None) is False
    assert client_has_pdn_consent({}) is False
    assert (
        client_has_pdn_consent(
            {
                "pdn_consent_version": "pdn-consent-2026-08-22",
                "pdn_consent_accepted_at": "2026-09-01T00:00:00Z",
            }
        )
        is True
    )
