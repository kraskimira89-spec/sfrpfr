"""Unit-тесты secure action links (MAX-first Sprint 1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from sfrfr.secure_links.errors import SecureLinkDenied, SecureLinksDisabled
from sfrfr.secure_links.service import SecureActionLinkService, StoredSecureLink
from sfrfr.secure_links.token import generate_raw_token, hash_token, token_prefix


class _MemRepo:
    def __init__(self) -> None:
        self.links: dict[str, dict[str, Any]] = {}
        self.by_hash: dict[str, str] = {}
        self.events: list[dict[str, Any]] = []

    def insert_link(self, row: dict[str, Any]) -> dict[str, Any]:
        stored = dict(row)
        assert "raw_token" not in stored
        self.links[stored["id"]] = stored
        self.by_hash[stored["token_hash"]] = stored["id"]
        return dict(stored)

    def get_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        lid = self.by_hash.get(token_hash)
        return dict(self.links[lid]) if lid and lid in self.links else None

    def get_by_id(self, link_id: str) -> dict[str, Any] | None:
        row = self.links.get(link_id)
        return dict(row) if row else None

    def update_link(self, link_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        self.links.setdefault(link_id, {"id": link_id}).update(fields)
        return dict(self.links[link_id])

    def list_active_for_case_purpose(
        self, case_id: str, purpose: str
    ) -> list[dict[str, Any]]:
        return [
            dict(r)
            for r in self.links.values()
            if r.get("case_id") == case_id
            and r.get("purpose") == purpose
            and r.get("status") == "active"
        ]

    def insert_event(self, row: dict[str, Any]) -> dict[str, Any]:
        self.events.append(dict(row))
        return dict(row)


@pytest.fixture
def pepper() -> bytes:
    return b"test-secure-link-pepper"


@pytest.fixture
def clock() -> dict[str, datetime]:
    return {"now": datetime(2026, 8, 25, 12, 0, 0, tzinfo=UTC)}


@pytest.fixture
def svc(pepper: bytes, clock: dict[str, datetime]) -> tuple[SecureActionLinkService, _MemRepo]:
    repo = _MemRepo()
    service = SecureActionLinkService(
        repo,
        enabled=True,
        pepper=pepper,
        now_fn=lambda: clock["now"],
    )
    return service, repo


def test_create_verify_ok(svc: tuple[SecureActionLinkService, _MemRepo]) -> None:
    service, repo = svc
    case_id = str(uuid4())
    issued = service.create(case_id=case_id, purpose="consent", ttl_hours=24, max_uses=2)
    assert issued.raw_token
    assert issued.token_prefix == token_prefix(issued.raw_token)

    stored = service.verify(issued.raw_token, purpose="consent")
    assert stored.id == issued.id
    assert stored.purpose == "consent"
    assert stored.case_id == case_id
    assert "raw_token" not in stored.storage_dict()
    assert issued.raw_token not in str(repo.links[issued.id])


def test_raw_token_not_in_stored_representation(
    svc: tuple[SecureActionLinkService, _MemRepo],
) -> None:
    service, repo = svc
    issued = service.create(case_id=str(uuid4()), purpose="upload")
    row = repo.links[issued.id]
    blob = str(row)
    assert issued.raw_token not in blob
    assert "raw_token" not in row
    view = StoredSecureLink(
        id=issued.id,
        token_hash=row["token_hash"],
        token_prefix=row["token_prefix"],
        purpose="upload",
        status="active",
        case_id=row["case_id"],
        max_uses=1,
        use_count=0,
        expires_at=datetime.fromisoformat(row["expires_at"]),
    )
    assert issued.raw_token not in str(view.storage_dict())


def test_expired_denied(
    svc: tuple[SecureActionLinkService, _MemRepo],
    clock: dict[str, datetime],
) -> None:
    service, _ = svc
    issued = service.create(case_id=str(uuid4()), purpose="pay", ttl_hours=1)
    clock["now"] = clock["now"] + timedelta(hours=2)
    with pytest.raises(SecureLinkDenied) as exc:
        service.verify(issued.raw_token, purpose="pay")
    assert exc.value.reason == "expired"


def test_revoked_denied(svc: tuple[SecureActionLinkService, _MemRepo]) -> None:
    service, _ = svc
    issued = service.create(case_id=str(uuid4()), purpose="view_pdf")
    service.revoke(issued.id, reason="test")
    with pytest.raises(SecureLinkDenied) as exc:
        service.verify(issued.raw_token, purpose="view_pdf")
    assert exc.value.reason == "revoked"


def test_max_uses_denied(svc: tuple[SecureActionLinkService, _MemRepo]) -> None:
    service, _ = svc
    issued = service.create(case_id=str(uuid4()), purpose="consent", max_uses=1)
    service.verify(issued.raw_token, purpose="consent", consume=True)
    with pytest.raises(SecureLinkDenied) as exc:
        service.verify(issued.raw_token, purpose="consent")
    assert exc.value.reason in ("consumed", "max_uses")


def test_wrong_purpose_denied(svc: tuple[SecureActionLinkService, _MemRepo]) -> None:
    service, _ = svc
    issued = service.create(case_id=str(uuid4()), purpose="consent")
    with pytest.raises(SecureLinkDenied) as exc:
        service.verify(issued.raw_token, purpose="upload")
    assert exc.value.reason == "wrong_purpose"


def test_flag_off_blocks_create_and_verify(pepper: bytes) -> None:
    repo = _MemRepo()
    service = SecureActionLinkService(repo, enabled=False, pepper=pepper)
    with pytest.raises(SecureLinksDisabled):
        service.create(case_id=str(uuid4()), purpose="consent")
    with pytest.raises(SecureLinksDisabled):
        service.verify("any-token", purpose="consent")
    assert repo.links == {}


def test_hash_uses_pepper(pepper: bytes) -> None:
    raw = generate_raw_token()
    a = hash_token(raw, pepper=pepper)
    b = hash_token(raw, pepper=b"other-pepper")
    assert a != b
    assert len(a) == 64
    assert a == hash_token(raw, pepper=pepper)


def test_supersede_old_link(svc: tuple[SecureActionLinkService, _MemRepo]) -> None:
    service, repo = svc
    case_id = str(uuid4())
    first = service.create(case_id=case_id, purpose="upload")
    second = service.create(case_id=case_id, purpose="upload")
    assert repo.links[first.id]["status"] == "superseded"
    assert repo.links[second.id]["status"] == "active"
    with pytest.raises(SecureLinkDenied) as exc:
        service.verify(first.raw_token, purpose="upload")
    assert exc.value.reason == "superseded"
    ok = service.verify(second.raw_token, purpose="upload")
    assert ok.id == second.id
