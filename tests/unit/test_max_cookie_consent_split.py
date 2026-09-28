"""«Начать» в MAX фиксирует только согласие на ПДн, не на cookies сайта (152-ФЗ: отдельно)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sfrfr.db.case_repository import CURRENT_CONSENT_VERSION
from sfrfr.services import client_pdn_consent as cpc

CASE_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


class _Query:
    def __init__(self, client: _Client, name: str) -> None:
        self.client = client
        self.name = name
        self.op: str | None = None
        self.payload: Any = None

    def insert(self, payload: Any) -> _Query:
        self.op, self.payload = "insert", payload
        return self

    def update(self, payload: Any) -> _Query:
        self.op, self.payload = "update", payload
        return self

    def __getattr__(self, _attr: str):  # select/eq/limit
        return lambda *_a, **_k: self

    def execute(self) -> SimpleNamespace:
        if self.op:
            self.client.writes.append((self.op, self.name, dict(self.payload)))
            return SimpleNamespace(data=[])
        return SimpleNamespace(data=self.client.rows.get(self.name, []))


class _Client:
    def __init__(self, rows: dict[str, list[dict]] | None = None) -> None:
        self.writes: list[tuple[str, str, dict]] = []
        self.rows = rows or {}

    def table(self, name: str) -> _Query:
        return _Query(self, name)


class _Repo:
    def __init__(self, client: _Client) -> None:
        self.client = client

    def has_consent(self, _case_id: str) -> bool:
        return False

    def accept_consent(self, case_id: str, *, version: str, **_kw: Any) -> dict:
        self.client.writes.append(("insert", "consents", {"case_id": case_id, "version": version}))
        return {}


def test_start_writes_pdn_but_not_cookie_consent(monkeypatch) -> None:
    client = _Client()
    monkeypatch.setattr("sfrfr.db.session.get_supabase_client", lambda: client)
    monkeypatch.setattr("sfrfr.db.case_repository.CaseRepository", lambda: _Repo(client))

    cpc.accept_pdn_once(case_id=CASE_ID, max_user_id="777")

    client_updates = [p for op, t, p in client.writes if op == "update" and t == "clients"]
    assert client_updates, "ПДн-согласие клиента должно быть записано"
    for payload in client_updates:
        assert payload["pdn_consent_version"] == CURRENT_CONSENT_VERSION
        assert payload["pdn_consent_accepted_at"]
        assert not any(k.startswith("cookie_consent") for k in payload)

    versions = [p["version"] for op, t, p in client.writes if t == "consents"]
    assert versions == [CURRENT_CONSENT_VERSION]


def test_inherited_case_consent_has_no_cookie_row(monkeypatch) -> None:
    client = _Client(
        rows={
            "clients": [
                {
                    "id": "c1",
                    "pdn_consent_version": CURRENT_CONSENT_VERSION,
                    "pdn_consent_accepted_at": "2026-09-28T00:00:00+00:00",
                }
            ]
        }
    )
    monkeypatch.setattr("sfrfr.db.case_repository.CaseRepository", lambda: _Repo(client))

    assert cpc.ensure_case_consent_from_client(case_id=CASE_ID, client_id="c1") is True

    versions = [p["version"] for op, t, p in client.writes if t == "consents"]
    assert versions == [CURRENT_CONSENT_VERSION]
