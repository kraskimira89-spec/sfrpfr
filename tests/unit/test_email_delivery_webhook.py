"""Unit-тесты webhook доставки e-mail (ТЗ-31) без живого Supabase."""

from __future__ import annotations

import base64
from typing import Any

from sfrfr.integrations.email_webhooks.postmark import (
    parse_postmark_payload,
    verify_postmark_basic_auth,
)
from sfrfr.services.email_delivery_normalize import (
    contact_key_for_email,
    event_fingerprint,
    recipient_domain,
    redact_payload,
)
from sfrfr.services.email_delivery_webhook import EmailDeliveryWebhookService


def test_basic_auth_ok_and_fail() -> None:
    token = base64.b64encode(b"hook:secret").decode("ascii")
    assert verify_postmark_basic_auth(
        f"Basic {token}", username="hook", password="secret"
    )
    assert not verify_postmark_basic_auth(
        f"Basic {token}", username="hook", password="wrong"
    )
    assert not verify_postmark_basic_auth(None, username="hook", password="secret")


def test_redact_strips_email_and_keeps_domain() -> None:
    raw = {
        "Recipient": "ivan@mail.ru",
        "Details": "ok for ivan@mail.ru case 7c377c03-53df-4c10-a59c-2baeea4fe6e4",
        "MessageStream": "outbound",
        "TypeCode": 250,
    }
    domain = recipient_domain("ivan@mail.ru")
    out = redact_payload(raw, recipient_domain_value=domain)
    assert out["recipient_domain"] == "mail.ru"
    assert "ivan@" not in str(out)
    assert "[email]" in str(out.get("Details") or "")
    assert "[id]" in str(out.get("Details") or "")


def test_contact_key_is_hash_not_email() -> None:
    key = contact_key_for_email("Client@Example.COM")
    assert key.startswith("email:")
    assert "example.com" not in key
    assert "@" not in key


def test_parse_delivery_and_hard_bounce() -> None:
    delivery = parse_postmark_payload(
        {
            "RecordType": "Delivery",
            "MessageID": "msg-1",
            "Recipient": "a@mail.ru",
            "DeliveredAt": "2026-08-23T14:32:11Z",
            "MessageStream": "outbound",
        }
    )
    assert len(delivery) == 1
    assert delivery[0].event_type == "delivered"
    assert delivery[0].recipient_domain == "mail.ru"
    assert "a@" not in str(delivery[0].payload_redacted)

    bounce = parse_postmark_payload(
        {
            "RecordType": "Bounce",
            "MessageID": "msg-2",
            "Recipient": "b@mail.ru",
            "Type": "HardBounce",
            "TypeCode": 1,
            "BouncedAt": "2026-08-23T14:33:00Z",
            "Description": "bad mailbox",
        }
    )
    assert bounce[0].event_type == "hard_bounce"


def test_soft_bounce_not_hard() -> None:
    soft = parse_postmark_payload(
        {
            "RecordType": "Bounce",
            "MessageID": "msg-3",
            "Recipient": "c@mail.ru",
            "Type": "Transient",
            "TypeCode": 2,
            "BouncedAt": "2026-08-23T14:34:00Z",
        }
    )
    assert soft[0].event_type == "soft_bounce"


class _MemDeliveryRepo:
    def __init__(self) -> None:
        self.events: dict[str, dict[str, Any]] = {}
        self.jobs: dict[str, dict[str, Any]] = {}
        self.by_mid: dict[str, str] = {}
        self.contacts: dict[tuple[str, str], dict[str, Any]] = {}
        self.cancelled: list[str] = []

    def fingerprint_exists(self, fingerprint: str) -> bool:
        return any(e.get("event_fingerprint") == fingerprint for e in self.events.values())

    def insert_event(self, row: dict[str, Any]) -> dict[str, Any]:
        self.events[row["id"]] = dict(row)
        return self.events[row["id"]]

    def get_job_by_provider_message_id(self, message_id: str) -> dict[str, Any] | None:
        jid = self.by_mid.get(message_id)
        return self.jobs.get(jid) if jid else None

    def update_job(self, job_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        self.jobs.setdefault(job_id, {"id": job_id}).update(fields)
        return self.jobs[job_id]

    def cancel_pending_email_jobs(self, *, contact_key: str | None, case_id: str | None) -> int:
        n = 0
        for job in self.jobs.values():
            if job.get("channel") != "email":
                continue
            if contact_key and job.get("recipient_contact_key") != contact_key:
                continue
            if job.get("status") in ("draft", "queued", "sent"):
                job["status"] = "cancelled"
                self.cancelled.append(str(job["id"]))
                n += 1
        return n

    def upsert_contact_status(
        self,
        *,
        contact_key: str,
        channel: str,
        status: str,
        reason: str | None,
    ) -> dict[str, Any]:
        row = {"contact_key": contact_key, "channel": channel, "status": status, "reason": reason}
        self.contacts[(contact_key, channel)] = row
        return row


def test_idempotent_and_delivered_does_not_open_pdf() -> None:
    repo = _MemDeliveryRepo()
    job = {
        "id": "j1",
        "case_id": "c1",
        "channel": "email",
        "status": "sent",
        "recipient_contact_key": "email:abc",
        "diagnostic_result_id": "r1",
    }
    repo.jobs["j1"] = job
    repo.by_mid["msg-d"] = "j1"
    svc = EmailDeliveryWebhookService(repo=repo)  # type: ignore[arg-type]
    events = parse_postmark_payload(
        {
            "RecordType": "Delivery",
            "MessageID": "msg-d",
            "Recipient": "x@mail.ru",
            "DeliveredAt": "2026-08-23T14:32:11Z",
        }
    )
    first = svc.process_events(events)
    second = svc.process_events(events)
    assert first["stored"] == 1
    assert second["duplicates"] == 1
    assert repo.jobs["j1"]["status"] == "delivered"
    # PDF status not on job — webhook must not invent opened on result
    assert "opened" not in str(repo.jobs["j1"])


def test_hard_bounce_blocks_and_cancels() -> None:
    repo = _MemDeliveryRepo()
    repo.jobs["j1"] = {
        "id": "j1",
        "case_id": "c1",
        "channel": "email",
        "status": "sent",
        "recipient_contact_key": "email:abc",
    }
    repo.jobs["j2"] = {
        "id": "j2",
        "case_id": "c1",
        "channel": "email",
        "status": "draft",
        "recipient_contact_key": "email:abc",
    }
    repo.by_mid["msg-b"] = "j1"
    svc = EmailDeliveryWebhookService(repo=repo)  # type: ignore[arg-type]
    events = parse_postmark_payload(
        {
            "RecordType": "Bounce",
            "MessageID": "msg-b",
            "Recipient": "x@mail.ru",
            "Type": "HardBounce",
            "TypeCode": 1,
            "BouncedAt": "2026-08-23T15:00:00Z",
        }
    )
    out = svc.process_events(events)
    assert out["transitions"] == 1
    assert repo.jobs["j1"]["status"] == "hard_bounce"
    assert repo.contacts[("email:abc", "email")]["status"] == "hard_bounce"
    assert "j2" in repo.cancelled


def test_unknown_message_id_stored_unmatched() -> None:
    repo = _MemDeliveryRepo()
    svc = EmailDeliveryWebhookService(repo=repo)  # type: ignore[arg-type]
    events = parse_postmark_payload(
        {
            "RecordType": "Delivery",
            "MessageID": "unknown-mid",
            "Recipient": "z@mail.ru",
            "DeliveredAt": "2026-08-23T14:32:11Z",
        }
    )
    out = svc.process_events(events)
    assert out["unmatched"] == 1
    assert out["stored"] == 1
    ev = next(iter(repo.events.values()))
    assert ev["unmatched"] is True
    assert ev["notification_job_id"] is None


def test_fingerprint_stable() -> None:
    a = event_fingerprint(
        provider="postmark",
        provider_event_id="t1",
        provider_message_id="m1",
        raw_type="Delivery",
        timestamp="2026-08-23T14:32:11+00:00",
    )
    b = event_fingerprint(
        provider="postmark",
        provider_event_id="t1",
        provider_message_id="m1",
        raw_type="Delivery",
        timestamp="2026-08-23T14:32:11+00:00",
    )
    assert a == b
    assert len(a) == 64
