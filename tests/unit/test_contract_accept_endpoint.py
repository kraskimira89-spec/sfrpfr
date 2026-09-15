"""B1: endpoint акцепта оферты — валидация версии и признак договора в work map."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from sfrfr.api.routes import portal as portal_route
from sfrfr.api.routes.portal import accept_contract
from sfrfr.api.schemas.portal import ContractAcceptRequest

SUPPORTED = "offer-2026-09-09"


class FakePrincipal:
    user_id = "user-1"
    email = "client@example.ru"
    is_staff = False

    def audit_actor_id(self) -> str:
        return "user-1"


class FakeRepo:
    def __init__(self) -> None:
        self.accepted: list[dict[str, Any]] = []

    def require_case(self, _principal: Any, case_id: str) -> dict:
        return {"id": case_id}

    def accept_contract(self, case_id: str, **kwargs: Any) -> dict:
        self.accepted.append({"case_id": case_id, **kwargs})
        return {"id": "ca-1", "case_id": case_id, "offer_version": kwargs["offer_version"]}


@pytest.fixture()
def repo(monkeypatch: pytest.MonkeyPatch) -> FakeRepo:
    fake = FakeRepo()
    monkeypatch.setattr(portal_route, "_repo", lambda: fake)
    return fake


def test_accept_contract_supported_version(repo: FakeRepo) -> None:
    row = accept_contract("c1", ContractAcceptRequest(offer_version=SUPPORTED), FakePrincipal())  # type: ignore[arg-type]
    assert row["id"] == "ca-1"
    assert len(repo.accepted) == 1
    assert repo.accepted[0]["offer_version"] == SUPPORTED


def test_accept_contract_default_version_is_supported(repo: FakeRepo) -> None:
    accept_contract("c1", ContractAcceptRequest(), FakePrincipal())  # type: ignore[arg-type]
    assert repo.accepted[0]["offer_version"] == SUPPORTED


def test_accept_contract_rejects_unknown_version(repo: FakeRepo) -> None:
    with pytest.raises(HTTPException) as exc:
        accept_contract(
            "c1",
            ContractAcceptRequest(offer_version="offer-2099-01-01"),
            FakePrincipal(),  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 400
    assert isinstance(exc.value.detail, str)
    assert "оферт" in exc.value.detail.lower()
    # Состояние не изменилось: акцепт не выполнен
    assert repo.accepted == []


def test_accept_contract_staff_forbidden(repo: FakeRepo) -> None:
    staff = FakePrincipal()
    staff.is_staff = True
    with pytest.raises(HTTPException) as exc:
        accept_contract("c1", ContractAcceptRequest(offer_version=SUPPORTED), staff)  # type: ignore[arg-type]
    assert exc.value.status_code == 403
    assert repo.accepted == []


def _full_docs_case() -> dict:
    return {
        "id": "c1",
        "pipeline_status": "intake",
        "b2c_status": "consent_accepted",
        "documents": [
            {"id": "a", "doc_type": "ils"},
            {"id": "b", "doc_type": "workbook"},
        ],
        "checklist_items": [],
    }


def test_work_map_passes_contract_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(portal_route, "_repo", lambda: FakeRepo())
    work = portal_route._work_map(
        _full_docs_case(),
        consent_accepted=True,
        orders=[],
        scenario_rows=[],
        contract_accepted=False,
    )
    assert work["cta_key"] == "contract"
    work_accepted = portal_route._work_map(
        _full_docs_case(),
        consent_accepted=True,
        orders=[],
        scenario_rows=[],
        contract_accepted=True,
    )
    assert work_accepted["cta_key"] != "contract"
