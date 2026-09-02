"""Unit-тесты Yandex Cloud Postbox webhook / send helpers."""

from __future__ import annotations

import base64
import json

from sfrfr.integrations.email_webhooks.postbox import (
    extract_postbox_events,
    parse_postbox_payload,
    verify_postbox_basic_auth,
)
from sfrfr.integrations.yandex_postbox.aws_sigv4 import sigv4_headers


def test_postbox_basic_auth() -> None:
    token = base64.b64encode(b"pb:secret").decode("ascii")
    assert verify_postbox_basic_auth(f"Basic {token}", username="pb", password="secret")
    assert not verify_postbox_basic_auth(f"Basic {token}", username="pb", password="x")


def test_parse_delivery_and_hard_bounce() -> None:
    delivery = parse_postbox_payload(
        {
            "eventType": "Delivery",
            "mail": {
                "timestamp": "2024-04-25T18:05:04.84108+03:00",
                "messageId": "pb-msg-1",
                "commonHeaders": {
                    "to": ["Name <a@mail.ru>"],
                    "messageId": "pb-msg-1",
                },
            },
            "delivery": {
                "timestamp": "2024-04-25T18:05:14.84107+03:00",
                "recipients": ["a@mail.ru"],
            },
            "eventId": "pb-msg-1:0",
        }
    )
    assert len(delivery) == 1
    assert delivery[0].provider == "yandex_postbox"
    assert delivery[0].event_type == "delivered"
    assert delivery[0].provider_message_id == "pb-msg-1"
    assert delivery[0].recipient_domain == "mail.ru"
    assert "a@" not in str(delivery[0].payload_redacted)

    bounce = parse_postbox_payload(
        {
            "eventType": "Bounce",
            "mail": {"messageId": "pb-msg-2", "timestamp": "2024-04-25T18:08:04+03:00"},
            "bounce": {
                "bounceType": "Permanent",
                "bounceSubType": "Undetermined",
                "timestamp": "2024-04-25T18:08:04+03:00",
                "bouncedRecipients": [
                    {"emailAddress": "b@mail.ru", "status": "5.1.1"},
                ],
            },
            "eventId": "pb-msg-2:1",
        }
    )
    assert bounce[0].event_type == "hard_bounce"
    assert bounce[0].recipient_domain == "mail.ru"


def test_send_maps_to_accepted() -> None:
    ev = parse_postbox_payload(
        {
            "eventType": "Send",
            "mail": {"messageId": "pb-send", "timestamp": "2024-04-25T18:05:04+03:00"},
            "send": {},
            "eventId": "pb-send:0",
        }
    )[0]
    assert ev.event_type == "accepted"


def test_yds_wrapper_base64() -> None:
    inner = {
        "eventType": "Delivery",
        "mail": {"messageId": "wrapped-1", "timestamp": "2024-04-25T18:05:04Z"},
        "delivery": {"timestamp": "2024-04-25T18:05:14Z", "recipients": ["c@example.com"]},
        "eventId": "wrapped-1:0",
    }
    encoded = base64.b64encode(json.dumps(inner).encode()).decode()
    wrapper = {
        "messages": [
            {"details": {"message": {"data": encoded}}},
        ]
    }
    assert len(extract_postbox_events(wrapper)) == 1
    events = parse_postbox_payload(wrapper)
    assert events[0].provider_message_id == "wrapped-1"
    assert events[0].event_type == "delivered"


def test_sigv4_headers_stable_shape() -> None:
    headers = sigv4_headers(
        method="POST",
        url_path="/v2/email/outbound-emails",
        host="postbox.cloud.yandex.net",
        body=b'{"FromEmailAddress":"a@b.c"}',
        access_key_id="AKIA_TEST",
        secret_access_key="secret_test_key",
    )
    assert headers["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=AKIA_TEST/")
    assert "Signature=" in headers["Authorization"]
    assert headers["Host"] == "postbox.cloud.yandex.net"
    assert headers["X-Amz-Date"]
    assert headers["X-Amz-Content-Sha256"]
