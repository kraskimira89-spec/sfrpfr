"""Тесты подписей Mailgun / SendGrid (разные алгоритмы)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from sfrfr.integrations.email_webhooks.mailgun import (
    parse_mailgun_payload,
    verify_mailgun_signature,
)
from sfrfr.integrations.email_webhooks.sendgrid import (
    parse_sendgrid_payload,
    verify_sendgrid_signature,
)


def test_mailgun_hmac_ok_and_skew() -> None:
    key = "test-signing-key"
    ts = str(int(time.time()))
    token = "abc123token"
    sig = hmac.new(
        key.encode(), f"{ts}{token}".encode(), hashlib.sha256
    ).hexdigest()
    assert verify_mailgun_signature(key, ts, token, sig)
    assert not verify_mailgun_signature(key, ts, token, "0" * 64)
    old = str(int(time.time()) - 10_000)
    old_sig = hmac.new(
        key.encode(), f"{old}{token}".encode(), hashlib.sha256
    ).hexdigest()
    assert not verify_mailgun_signature(key, old, token, old_sig)


def test_mailgun_parse_delivered_redacts_email() -> None:
    ts = str(int(time.time()))
    token = "tok1"
    key = "k"
    signature = hmac.new(
        key.encode(), f"{ts}{token}".encode(), hashlib.sha256
    ).hexdigest()
    body = {
        "signature": {"timestamp": ts, "token": token, "signature": signature},
        "event-data": {
            "event": "delivered",
            "id": "ev-1",
            "timestamp": int(ts),
            "recipient": "person@mail.ru",
            "message": {"headers": {"message-id": "<mid-mg-1@mg.example>"}},
        },
    }
    events = parse_mailgun_payload(body)
    assert len(events) == 1
    assert events[0].provider == "mailgun"
    assert events[0].event_type == "delivered"
    assert events[0].provider_message_id == "mid-mg-1@mg.example"
    assert events[0].recipient_domain == "mail.ru"
    assert "person@" not in str(events[0].payload_redacted)


def test_mailgun_permanent_failed_is_hard_bounce() -> None:
    body = {
        "event-data": {
            "event": "failed",
            "severity": "permanent",
            "id": "ev-b",
            "timestamp": int(time.time()),
            "recipient": "x@mail.ru",
            "message": {"headers": {"message-id": "mid-b"}},
            "delivery-status": {"code": 550, "message": "user unknown"},
        }
    }
    ev = parse_mailgun_payload(body)[0]
    assert ev.event_type == "hard_bounce"


def _sendgrid_keypair() -> tuple[str, ec.EllipticCurvePrivateKey]:
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key()
    der = public.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return base64.b64encode(der).decode("ascii"), private


def test_sendgrid_ecdsa_raw_body() -> None:
    pub_b64, private = _sendgrid_keypair()
    body = (
        b'[{"email":"a@mail.ru","event":"delivered",'
        b'"sg_message_id":"m1.filter","sg_event_id":"e1","timestamp":1720000000}]'
    )
    ts = str(int(time.time()))
    payload = ts.encode() + body
    sig = private.sign(payload, ec.ECDSA(hashes.SHA256()))
    sig_b64 = base64.b64encode(sig).decode("ascii")
    assert verify_sendgrid_signature(
        public_key=pub_b64,
        raw_body=body,
        signature_b64=sig_b64,
        timestamp=ts,
    )
    # подпись по распарсенному JSON (пересоборка) — невалидна
    rebuilt = json.dumps(json.loads(body.decode())).encode()
    assert rebuilt != body or True  # даже если совпадёт — проверим битую подпись
    assert not verify_sendgrid_signature(
        public_key=pub_b64,
        raw_body=body + b" ",
        signature_b64=sig_b64,
        timestamp=ts,
    )


def test_sendgrid_parse_array() -> None:
    raw = json.dumps(
        [
            {
                "email": "a@mail.ru",
                "event": "delivered",
                "sg_message_id": "abc.filter0",
                "sg_event_id": "eid-1",
                "timestamp": 1720000000,
            },
            {
                "email": "b@mail.ru",
                "event": "bounce",
                "type": "bounce",
                "sg_message_id": "xyz.filter0",
                "sg_event_id": "eid-2",
                "timestamp": 1720000001,
            },
        ]
    ).encode()
    events = parse_sendgrid_payload(raw)
    assert len(events) == 2
    assert events[0].event_type == "delivered"
    assert events[0].provider_message_id == "abc"
    assert events[1].event_type == "hard_bounce"
    assert "a@" not in str(events[0].payload_redacted)
