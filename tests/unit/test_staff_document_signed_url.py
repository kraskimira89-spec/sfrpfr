"""Staff signed-url: local quarantine / needs_reupload / AV error."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from sfrfr.api.routes import portal as portal_routes
from sfrfr.security.auth import Principal, StaffRole
from sfrfr.services.document_upload import is_document_downloadable
from sfrfr.services.local_doc_download import reset_for_tests


def test_av_error_blocks_client_allows_staff() -> None:
    row = {
        "ingest_status": "manual_review",
        "antivirus_status": "error",
        "local_path": "quarantine/x/y.pdf",
    }
    assert is_document_downloadable(row) is False
    assert is_document_downloadable(row, allow_staff_preview=True) is True


def test_create_signed_url_staff_local_av_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Живой сценарий дела: local_path + needs_reupload/manual_review + AV error."""
    reset_for_tests()
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4 staff-smoke")

    case_id = "c3074452-ac27-4f43-b5ee-88af96792b17"
    doc_id = "538c5910-f2ac-4e29-bea8-7be3a62de30e"
    row = {
        "id": doc_id,
        "storage_path": f"quarantine/{case_id}/{doc_id}/document_1.pdf",
        "local_path": "quarantine/case/doc.pdf",
        "ingest_status": "manual_review",
        "mime_verified": "application/pdf",
        "doc_type": "workbook",
        "antivirus_status": "error",
    }

    repo = MagicMock()
    repo.require_case.return_value = {"id": case_id}
    repo.audit = MagicMock()
    monkeypatch.setattr(portal_routes, "_repo", lambda: repo)

    sb = MagicMock()
    chain = sb.table.return_value.select.return_value.eq.return_value.eq.return_value
    chain.limit.return_value.execute.return_value = SimpleNamespace(data=[row])
    monkeypatch.setattr(portal_routes, "get_supabase_client", lambda: sb)
    monkeypatch.setattr(
        portal_routes.CaseRepository,
        "_one_or_none",
        staticmethod(lambda resp: (resp.data or [None])[0]),
    )
    monkeypatch.setattr(
        "sfrfr.storage.local.path_from_uploads_relative",
        lambda _rel: pdf,
    )
    monkeypatch.setattr(
        portal_routes,
        "get_settings",
        lambda: SimpleNamespace(public_base_url="https://api.example.test"),
    )
    monkeypatch.setattr(
        "sfrfr.services.document_upload._audit_access",
        lambda *_a, **_k: None,
    )

    staff = Principal(
        user_id="staff-1",
        email="staff@example.test",
        role=StaffRole.EXPERT,
    )
    out = portal_routes.create_document_signed_url(case_id, doc_id, staff)
    assert "/api/portal/tmp-docs/" in out.url
    assert "response-content-disposition=inline" in out.url or "download=" in out.url

    token = out.url.split("/tmp-docs/")[1].split("?")[0]
    resp = portal_routes.download_tmp_local_document(token)
    assert resp.media_type == "application/pdf"
    assert Path(str(resp.path)).read_bytes().startswith(b"%PDF")


def test_create_signed_url_infected_still_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_for_tests()
    case_id = "c1"
    doc_id = "d1"
    row = {
        "id": doc_id,
        "storage_path": "local-pending/c1/d1/a.pdf",
        "local_path": "quarantine/c1/a.pdf",
        "ingest_status": "needs_reupload",
        "mime_verified": "application/pdf",
        "doc_type": "ils",
        "antivirus_status": "infected",
    }
    repo = MagicMock()
    repo.require_case.return_value = {"id": case_id}
    monkeypatch.setattr(portal_routes, "_repo", lambda: repo)
    sb = MagicMock()
    chain = sb.table.return_value.select.return_value.eq.return_value.eq.return_value
    chain.limit.return_value.execute.return_value = SimpleNamespace(data=[row])
    monkeypatch.setattr(portal_routes, "get_supabase_client", lambda: sb)
    monkeypatch.setattr(
        portal_routes.CaseRepository,
        "_one_or_none",
        staticmethod(lambda resp: (resp.data or [None])[0]),
    )
    staff = Principal(user_id="s", email="s@t", role=StaffRole.ADMIN)
    with pytest.raises(HTTPException) as exc:
        portal_routes.create_document_signed_url(case_id, doc_id, staff)
    assert exc.value.status_code == 403
