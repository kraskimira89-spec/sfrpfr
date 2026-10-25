"""Удаление документа сотрудником: файл, строка и производные данные.

Журналы доступа и загрузок не трогаем — это аудит. Файлы, на которые
опирается результат (PDF разбора, доказательства), удалять нельзя.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sfrfr.security.integrations import PRIVATE_STORAGE_BUCKET

logger = logging.getLogger(__name__)

# Производные данные документа: без него они бессмысленны.
_DERIVED_TABLES = ("document_ingest_jobs", "case_document_checksums", "labor_timeline_drafts")
# Документ — основание результата: удаление сломает доказательную базу.
_EVIDENCE_TABLES = ("result_evidence", "diagnostic_results")


class DocumentDeleteError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _rows(client: Any, table: str, **eq: Any) -> list[dict[str, Any]]:
    query = client.table(table).select("*")
    for col, val in eq.items():
        query = query.eq(col, val)
    return list(query.execute().data or [])


def _remove_local_file(path: str, case_id: str) -> None:
    """Локальная копия на сервере — только файл внутри папки этого дела."""
    if not path or case_id not in path:
        return
    try:
        p = Path(path)
        if p.is_file():
            p.unlink()
    except OSError as exc:
        logger.info("local file remove skipped doc_path=%s err=%s", path[-40:], type(exc).__name__)


def delete_case_document(client: Any, *, case_id: str, document_id: str) -> dict[str, Any]:
    found = _rows(client, "documents", id=document_id, case_id=case_id)
    if not found:
        raise DocumentDeleteError(404, "Документ не найден")
    row = found[0]
    if str(row.get("doc_type") or "").lower() == "diagnosis_report":
        raise DocumentDeleteError(409, "PDF разбора клиента удалить нельзя")
    for table in _EVIDENCE_TABLES:
        if _rows(client, table, document_id=document_id):
            raise DocumentDeleteError(409, "Файл используется в результате — удалить нельзя")

    path = str(row.get("storage_path") or "")
    if path:
        try:
            client.storage.from_(PRIVATE_STORAGE_BUCKET).remove([path])
        except Exception as exc:  # noqa: BLE001
            logger.info("storage remove skipped: %s", type(exc).__name__)
    _remove_local_file(str(row.get("local_path") or ""), case_id)

    for table in _DERIVED_TABLES:
        client.table(table).delete().eq("document_id", document_id).execute()
    client.table("documents").update({"replaces_document_id": None}).eq(
        "replaces_document_id", document_id
    ).execute()
    client.table("documents").delete().eq("id", document_id).eq("case_id", case_id).execute()
    return {"deleted": document_id}
