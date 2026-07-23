"""Тесты паритета каналов ТЗ-09: link token, preferences, notification CTA, MAX principal."""

from __future__ import annotations

from sfrfr.integrations.client_channels.notifications import notification_channel_links
from sfrfr.security.auth import Principal
from sfrfr.security.max_link_token import make_max_link_token, verify_max_link_token
from sfrfr.security.max_webapp import extract_max_user_id


def test_max_link_token_roundtrip() -> None:
    token = make_max_link_token("6407832")
    assert verify_max_link_token(token) == "6407832"
    assert verify_max_link_token("bad.token.here") is None
    assert verify_max_link_token("a.1.deadbeef") is None


def test_notification_links_prefer_max() -> None:
    payload = notification_channel_links(
        preferred_channel="max_miniapp",
        max_linked=True,
        case_id="11111111-2222-3333-4444-555555555555",
    )
    assert payload["links"][0]["channel"] == "max_miniapp"
    assert "case=" in payload["links"][1]["url"]
    assert "не гарантирован" in payload["warning"].lower() or "СФР" in payload["warning"]


def test_notification_links_prefer_web() -> None:
    payload = notification_channel_links(
        preferred_channel="web_cabinet",
        max_linked=False,
    )
    assert payload["links"][0]["channel"] == "web_cabinet"


def test_notification_links_unlinked_uses_bot_url() -> None:
    payload = notification_channel_links(
        preferred_channel="max_miniapp",
        max_linked=False,
    )
    max_link = next(item for item in payload["links"] if item["channel"] == "max_miniapp")
    assert max_link["url"] == max_link["bot_url"]


def test_principal_max_only_audit_actor() -> None:
    p = Principal(
        user_id="max:99",
        email=None,
        role=None,
        max_user_id="99",
        auth_via="max",
    )
    assert p.is_max_only is True
    assert p.audit_actor_id() is None


def test_extract_user_and_openapi_routes() -> None:
    from sfrfr.api import create_app

    assert extract_max_user_id('user=%7B%22id%22%3A7%7D') == "7"
    paths = set(create_app().openapi()["paths"])
    assert "/api/portal/cases" in paths
    assert "/api/portal/me/notification-links" in paths
    assert "/api/portal/link/max" in paths
    assert "/api/portal/link/web-from-max" in paths
