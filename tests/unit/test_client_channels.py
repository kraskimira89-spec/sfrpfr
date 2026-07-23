"""Тесты разбора MAX initData и схем канала."""

from __future__ import annotations

from sfrfr.api.schemas.portal import PreferredChannel
from sfrfr.security.max_webapp import extract_max_user_id, parse_max_init_data, verify_max_init_data


def test_extract_max_user_id_from_init_data() -> None:
    init = 'user=%7B%22id%22%3A12345%2C%22first_name%22%3A%22A%22%7D&auth_date=1&hash=abc'
    assert extract_max_user_id(init) == "12345"


def test_extract_fallback() -> None:
    assert extract_max_user_id(None, fallback="99") == "99"
    assert extract_max_user_id("") is None


def test_parse_and_verify_roundtrip_shape() -> None:
    fields = parse_max_init_data("a=1&b=2&hash=deadbeef")
    assert fields["a"] == "1"
    assert fields["hash"] == "deadbeef"
    # без корректной подписи — False
    assert verify_max_init_data("a=1&hash=deadbeef", "token") is False


def test_preferred_channel_values() -> None:
    assert PreferredChannel.MAX_MINIAPP.value == "max_miniapp"
    assert PreferredChannel.WEB_CABINET.value == "web_cabinet"
