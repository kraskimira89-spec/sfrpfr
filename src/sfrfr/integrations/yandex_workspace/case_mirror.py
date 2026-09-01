"""Best-effort зеркало документов дела на Яндекс.Диск (SFRFR-cases)."""

from __future__ import annotations

import logging
from typing import Any

from sfrfr.integrations.yandex_workspace.disk import mirror_case_document as _mirror

logger = logging.getLogger(__name__)


def mirror_case_document_safe(
    case_id: str,
    filename: str,
    data: bytes,
    *,
    doc_type: str | None = None,
) -> dict[str, Any]:
    """Не бросает наружу: skipped / ok / error в dict + warning в лог при сбое."""
    dtype = str(doc_type or "").strip().lower()
    if dtype in {"bank_statement", "bank"}:
        return {"ok": False, "skipped": True, "reason": "bank_statement_no_mirror"}
    try:
        result = _mirror(case_id, filename, data)
    except Exception as exc:  # noqa: BLE001
        logger.warning("yandex disk case mirror failed: %s", exc)
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}
    if result.get("skipped"):
        return result
    if not result.get("ok"):
        logger.warning(
            "yandex disk case mirror not ok case_id=%s err=%s detail=%s",
            (case_id or "")[:36],
            result.get("error") or result.get("status_code"),
            (result.get("detail") or "")[:200],
        )
    return result
