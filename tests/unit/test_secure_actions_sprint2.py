"""Sprint 2: consent + view_pdf actions (unit, in-memory)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from sfrfr.db.case_repository import CURRENT_CONSENT_VERSION
from sfrfr.secure_links.actions import (
    grant_consent_via_token,
    issue_consent_link,
    issue_view_pdf_link,
    load_context,
)
from sfrfr.secure_links.errors import SecureLinkDenied, SecureLinksDisabled
from sfrfr.secure_links.service import SecureActionLinkService


class _MemRepo:
    def __init__(self) -> None:
        self.links: dict[str, dict[str, Any]] = {}
        self.by_hash: dict[str, str] = {}
        self.events: list[dict[str, Any]] = []

    def insert_link(self, row: dict[str, Any]) -> dict[str, Any]:
        stored = dict(row)
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
    return b"sprint2-pepper"


@pytest.fixture
def clock() -> dict[str, datetime]:
    return {"now": datetime(2026, 8, 25, 14, 0, 0, tzinfo=UTC)}


@pytest.fixture
def svc(pepper: bytes, clock: dict[str, datetime]) -> SecureActionLinkService:
    return SecureActionLinkService(
        _MemRepo(),
        enabled=True,
        pepper=pepper,
        now_fn=lambda: clock["now"],
    )


def test_issue_consent_requires_flag(svc: SecureActionLinkService) -> None:
    with patch("sfrfr.secure_links.actions.get_settings") as gs:
        gs.return_value = MagicMock(secure_action_links_enabled=False)
        with pytest.raises(SecureLinksDisabled):
            issue_consent_link(case_id="c1", service=svc)


def test_issue_and_load_consent_context(svc: SecureActionLinkService) -> None:
    settings = MagicMock(
        secure_action_links_enabled=True,
        secure_result_view_enabled=False,
        public_base_url="https://api.example",
        secure_link_pepper="",
        app_secret_key="x",
    )
    with (
        patch("sfrfr.secure_links.actions.get_settings", return_value=settings),
        patch("sfrfr.secure_links.urls.get_settings", return_value=settings),
        patch(
            "sfrfr.secure_links.actions.CaseRepository.has_consent",
            return_value=False,
        ),
        patch(
            "sfrfr.secure_links.actions.SecureActionLinkService",
            return_value=svc,
        ),
    ):
        issued = issue_consent_link(case_id="11111111-1111-1111-1111-111111111111")
        assert "raw_token_once" in issued
        assert "/api/portal/secure/" in issued["url"]
        assert "raw_token" not in issued.get("storage_dict", {})
        ctx = load_context(issued["raw_token_once"])
        assert ctx["purpose"] == "consent"
        assert ctx["consent_version"] == CURRENT_CONSENT_VERSION
        assert ctx["consent_already"] is False


def test_grant_consent_consumes_link(svc: SecureActionLinkService) -> None:
    settings = MagicMock(
        secure_action_links_enabled=True,
        public_base_url="https://api.example",
    )
    accept = MagicMock(return_value={"id": "cons1"})
    with (
        patch("sfrfr.secure_links.actions.get_settings", return_value=settings),
        patch("sfrfr.secure_links.urls.get_settings", return_value=settings),
        patch("sfrfr.secure_links.actions.SecureActionLinkService", return_value=svc),
        patch(
            "sfrfr.secure_links.actions.CaseRepository.has_consent",
            side_effect=[False, True],
        ),
        patch(
            "sfrfr.secure_links.actions.CaseRepository.accept_consent",
            accept,
        ),
    ):
        issued = issue_consent_link(case_id="11111111-1111-1111-1111-111111111111")
        raw = issued["raw_token_once"]
        out = grant_consent_via_token(raw, ip="127.0.0.1", user_agent="pytest")
        assert out["ok"] is True
        accept.assert_called_once()
        with pytest.raises(SecureLinkDenied) as exc:
            grant_consent_via_token(raw)
        assert exc.value.reason in ("consumed", "max_uses")


def test_view_pdf_requires_result_flag(svc: SecureActionLinkService) -> None:
    settings = MagicMock(
        secure_action_links_enabled=True,
        secure_result_view_enabled=False,
    )
    with patch("sfrfr.secure_links.actions.get_settings", return_value=settings):
        with pytest.raises(SecureLinksDisabled):
            issue_view_pdf_link(
                case_id="11111111-1111-1111-1111-111111111111",
                document_id="22222222-2222-2222-2222-222222222222",
                service=svc,
            )


def test_issue_view_pdf_ok(svc: SecureActionLinkService) -> None:
    settings = MagicMock(
        secure_action_links_enabled=True,
        secure_result_view_enabled=True,
        public_base_url="https://api.example",
    )
    with (
        patch("sfrfr.secure_links.actions.get_settings", return_value=settings),
        patch("sfrfr.secure_links.urls.get_settings", return_value=settings),
    ):
        issued = issue_view_pdf_link(
            case_id="11111111-1111-1111-1111-111111111111",
            document_id="22222222-2222-2222-2222-222222222222",
            service=svc,
        )
        assert issued["purpose"] == "view_pdf"
        assert "/pdf" in issued["pdf_url"]
