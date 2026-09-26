"""ТЗ-35 A3: запись согласия с версией, хэшем текста, max_user_id и сведениями события."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace
from typing import Any

from sfrfr.db.case_repository import CURRENT_CONSENT_VERSION, CaseRepository
from sfrfr.services import client_pdn_consent as cpc

CASE_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


class _Query:
    def __init__(self, client: _Client, name: str) -> None:
        self.client = client
        self.name = name
        self.payload: Any = None

    def insert(self, payload: Any) -> _Query:
        self.payload = payload
        return self

    def __getattr__(self, _attr: str):  # select/eq/update/limit/order
        return lambda *_a, **_k: self

    def execute(self) -> SimpleNamespace:
        if self.payload is not None:
            if self.name == "consents" and "text_sha256" in self.payload and self.client.old_schema:
                raise RuntimeError("column consents.text_sha256 does not exist")
            self.client.inserts.append((self.name, dict(self.payload)))
            return SimpleNamespace(data=[dict(self.payload)])
        return SimpleNamespace(data=[])


class _Client:
    def __init__(self, *, old_schema: bool = False) -> None:
        self.old_schema = old_schema
        self.inserts: list[tuple[str, dict]] = []

    def table(self, name: str) -> _Query:
        return _Query(self, name)


def _repo(client: _Client) -> CaseRepository:
    repo = CaseRepository.__new__(CaseRepository)
    repo.client = client
    return repo


def _consent_rows(client: _Client) -> list[dict]:
    return [p for name, p in client.inserts if name == "consents"]


def test_consent_text_sha256_matches_gate_text() -> None:
    digest = cpc.consent_text_sha256()
    assert digest == hashlib.sha256(cpc.CONSENT_GATE_TEXT.encode("utf-8")).hexdigest()
    assert len(digest) == 64


def test_accept_consent_stores_evidence() -> None:
    client = _Client()
    _repo(client).accept_consent(
        CASE_ID,
        version=CURRENT_CONSENT_VERSION,
        actor_id="system:max_start",
        client_id="c1",
        max_user_id="777",
        text_sha256="a" * 64,
        source="max_start",
        evidence={"update_type": "message_callback", "callback_id": "cb1"},
    )
    row = _consent_rows(client)[0]
    assert row["version"] == CURRENT_CONSENT_VERSION
    assert row["max_user_id"] == "777"
    assert row["client_id"] == "c1"
    assert row["text_sha256"] == "a" * 64
    assert row["source"] == "max_start"
    assert row["evidence"]["callback_id"] == "cb1"


def test_accept_consent_falls_back_on_old_schema() -> None:
    client = _Client(old_schema=True)
    _repo(client).accept_consent(
        CASE_ID,
        version=CURRENT_CONSENT_VERSION,
        actor_id="system:max_start",
        max_user_id="777",
        text_sha256="a" * 64,
    )
    rows = _consent_rows(client)
    assert rows == [{"case_id": CASE_ID, "version": CURRENT_CONSENT_VERSION}]


def test_accept_pdn_once_passes_evidence(monkeypatch) -> None:
    calls: list[dict] = []

    class _Repo:
        client = _Client()

        def has_consent(self, _case_id: str) -> bool:
            return False

        def accept_consent(self, case_id: str, **kw: Any) -> dict:
            calls.append({"case_id": case_id, **kw})
            return {}

    monkeypatch.setattr("sfrfr.db.case_repository.CaseRepository", _Repo)
    monkeypatch.setattr(cpc, "mark_client_pdn_consent", lambda **_kw: True)

    cpc.accept_pdn_once(
        case_id=CASE_ID,
        client_id="c1",
        max_user_id="777",
        evidence={"update_type": "message_callback"},
    )

    call = calls[0]
    assert call["max_user_id"] == "777"
    assert call["client_id"] == "c1"
    assert call["text_sha256"] == cpc.consent_text_sha256()
    assert call["source"] == "max_start"
    assert call["evidence"] == {"update_type": "message_callback"}


def test_start_button_sends_max_evidence(tmp_path, monkeypatch) -> None:
    from test_max_intake import _cb, _setup

    from sfrfr.integrations.max.handler import START_DIALOG_CALLBACK, handle_max_update

    bot = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "sfrfr.integrations.max.handler._client_has_pdn_consent",
        lambda _uid: False,
    )
    seen: list[dict] = []
    monkeypatch.setattr(
        "sfrfr.services.client_pdn_consent.accept_pdn_once",
        lambda **kw: seen.append(kw),
    )

    handle_max_update(_cb(301, START_DIALOG_CALLBACK, callback_id="cb-a3-301"), bot=bot)

    evidence = seen[0]["evidence"]
    assert evidence["channel"] == "max"
    assert evidence["via"] == "button"
    assert evidence["callback_id"] == "cb-a3-301"
    assert seen[0]["max_user_id"] == "301"
