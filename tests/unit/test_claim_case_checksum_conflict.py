"""Гонка claim: unique на реестре, documents ещё пуст — читать case_document_checksums."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from unittest.mock import MagicMock

import pytest

from sfrfr.services.document_deduplication import (
    claim_case_checksum,
    set_test_after_hash_lookup_barrier,
)


class _UniqueConflict(Exception):
    """Как PostgREST 23505."""


class _ChecksumTable:
    """Отдельные «соединения»: insert под lock как UNIQUE (case_id, checksum)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.rows: dict[tuple[str, str], dict[str, Any]] = {}
        self.insert_attempts = 0
        self.unique_conflicts = 0
        self.after_insert_attempt: threading.Barrier | None = None

    def insert(self, payload: dict[str, Any]) -> MagicMock:
        key = (str(payload["case_id"]), str(payload["checksum_sha256"]))
        with self._lock:
            self.insert_attempts += 1
            if key in self.rows:
                self.unique_conflicts += 1
                raise _UniqueConflict(
                    "duplicate key value violates unique constraint "
                    '\"case_document_checksums_pkey\" (23505)'
                )
            self.rows[key] = dict(payload)
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[payload])
        return chain

    def select(self, *_cols: str) -> _ChecksumSelect:
        return _ChecksumSelect(self)


class _ChecksumSelect:
    def __init__(self, table: _ChecksumTable) -> None:
        self._table = table
        self._case: str | None = None
        self._checksum: str | None = None

    def eq(self, col: str, value: object) -> _ChecksumSelect:
        if col == "case_id":
            self._case = str(value)
        elif col == "checksum_sha256":
            self._checksum = str(value)
        return self

    def limit(self, _n: int) -> _ChecksumSelect:
        return self

    def execute(self) -> MagicMock:
        key = (self._case or "", self._checksum or "")
        with self._table._lock:
            row = self._table.rows.get(key)
        data = [row] if row else []
        return MagicMock(data=data)


class _DocumentsTable:
    """Пустая documents: имитирует окно до insert победителя."""

    def select(self, *_a: object, **_k: object) -> _DocumentsSelect:
        return _DocumentsSelect()


class _DocumentsSelect:
    def eq(self, *_a: object, **_k: object) -> _DocumentsSelect:
        return self

    def order(self, *_a: object, **_k: object) -> _DocumentsSelect:
        return self

    def limit(self, *_a: object, **_k: object) -> _DocumentsSelect:
        return self

    def execute(self) -> MagicMock:
        return MagicMock(data=[])


class _FakeClient:
    def __init__(self) -> None:
        self.checksums = _ChecksumTable()
        self.documents = _DocumentsTable()

    def table(self, name: str) -> Any:
        if name == "case_document_checksums":
            return self.checksums
        if name == "documents":
            return self.documents
        raise AssertionError(f"unexpected table {name}")


@pytest.fixture()
def fake_client(monkeypatch: pytest.MonkeyPatch) -> _FakeClient:
    client = _FakeClient()
    monkeypatch.setattr(
        "sfrfr.db.session.get_supabase_client",
        lambda: client,
    )
    return client


def test_claim_conflict_reads_registry_while_documents_empty(
    fake_client: _FakeClient,
) -> None:
    case_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    checksum = "a" * 64
    winner = "11111111-1111-1111-1111-111111111111"
    loser = "22222222-2222-2222-2222-222222222222"

    assert (
        claim_case_checksum(
            case_id=case_id,
            checksum=checksum,
            size_bytes=10,
            document_id=winner,
        )
        == winner
    )
    # documents пуст — старый fallback вернул бы loser и создал бы дубль
    asserted = claim_case_checksum(
        case_id=case_id,
        checksum=checksum,
        size_bytes=10,
        document_id=loser,
    )
    assert asserted == winner
    assert len(fake_client.checksums.rows) == 1


def test_two_independent_claims_one_canonical(
    fake_client: _FakeClient,
) -> None:
    """Две независимые попытки claim: ровно один победитель, без зависания/исключений."""
    case_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    checksum = "b" * 64
    winner_candidate = "11111111-1111-1111-1111-111111111111"
    loser_candidate = "22222222-2222-2222-2222-222222222222"
    barrier = threading.Barrier(2, timeout=10)
    set_test_after_hash_lookup_barrier(barrier)

    results: list[str] = []
    errors: list[BaseException] = []

    def claim_one(doc_id: str) -> str:
        # Оба «соединения» доходят до claim одновременно (независимые «транзакции»)
        barrier.wait()
        return claim_case_checksum(
            case_id=case_id,
            checksum=checksum,
            size_bytes=42,
            document_id=doc_id,
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(claim_one, winner_candidate),
                pool.submit(claim_one, loser_candidate),
            ]
            for f in as_completed(futures):
                try:
                    results.append(f.result(timeout=15))
                except BaseException as exc:  # noqa: BLE001 — фиксируем любой сбой гонки
                    errors.append(exc)
    finally:
        set_test_after_hash_lookup_barrier(None)

    assert errors == [], f"гонка дала исключения: {errors!r}"
    assert len(results) == 2
    assert len(set(results)) == 1
    assert len(fake_client.checksums.rows) == 1
    assert fake_client.checksums.insert_attempts == 2
    assert fake_client.checksums.unique_conflicts == 1
    canonical = results[0]
    assert canonical in {winner_candidate, loser_candidate}
    assert fake_client.checksums.rows[(case_id, checksum)]["document_id"] == canonical
    # Проигравший не оставляет вторую строку реестра (нет «побочной» записи claim)
    loser = (
        loser_candidate if canonical == winner_candidate else winner_candidate
    )
    assert loser not in {
        r["document_id"] for r in fake_client.checksums.rows.values()
    }
