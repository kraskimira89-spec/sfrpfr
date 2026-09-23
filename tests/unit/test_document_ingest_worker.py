"""Тесты безопасного жизненного цикла quarantine-объекта."""

from __future__ import annotations

from types import SimpleNamespace

from sfrfr.services import document_ingest_worker


class _Storage:
    def __init__(self) -> None:
        self.uploads: list[str] = []
        self.removes: list[list[str]] = []

    def from_(self, _bucket: str) -> "_Storage":
        return self

    def upload(self, path: str, _data: bytes, _options: dict) -> None:
        self.uploads.append(path)

    def remove(self, paths: list[str]) -> None:
        self.removes.append(paths)


def test_verified_copy_keeps_quarantine_until_finalization() -> None:
    storage = _Storage()
    client = SimpleNamespace(storage=storage)

    document_ingest_worker._store_verified_copy(
        client,
        "quarantine/case/doc/file.pdf",
        "verified/case/doc/file.pdf",
        b"data",
        "application/pdf",
    )

    assert storage.uploads == ["verified/case/doc/file.pdf"]
    assert storage.removes == []
