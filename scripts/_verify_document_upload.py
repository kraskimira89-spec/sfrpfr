"""Проверка: create_quarantine_document пишет в documents + bucket (без ПДн)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path("/opt/sfrfr")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))

for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k, v.strip().strip("'").strip('"'))

from sfrfr.db.session import get_supabase_client  # noqa: E402
from sfrfr.services.document_ingest_worker import create_quarantine_document  # noqa: E402
from sfrfr.services.documents_schema import (  # noqa: E402
    clear_documents_schema_cache,
    documents_has_ingest_columns,
)

clear_documents_schema_cache()
client = get_supabase_client()
cases = client.table("cases").select("id").eq("is_test", True).limit(1).execute().data or []
if not cases:
    cases = client.table("cases").select("id").limit(1).execute().data or []
case_id = str(cases[0]["id"])
pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
name = f"verify-funnel-{uuid4().hex[:8]}.pdf"
row = create_quarantine_document(
    case_id=case_id,
    filename=name,
    data=pdf,
    content_type="application/pdf",
    doc_type="ils",
    uploaded_by=None,
    upload_source="max",
)
doc_id = str(row.get("id") or "")
check = (
    client.table("documents").select("id,storage_path,doc_type").eq("id", doc_id).limit(1).execute().data
    or []
)
out = {
    "ok": bool(check),
    "case_id_prefix": case_id[:8],
    "document_id": doc_id,
    "storage_path": (check[0] or {}).get("storage_path") if check else None,
    "ingest_schema": documents_has_ingest_columns(),
    "job_id": row.get("job_id"),
}
print(json.dumps(out, ensure_ascii=False, indent=2))
# cleanup test row + storage
if check:
    path = str(check[0].get("storage_path") or "")
    try:
        client.table("documents").delete().eq("id", doc_id).execute()
    except Exception as exc:  # noqa: BLE001
        out["cleanup_doc_err"] = str(exc)[:120]
    if path:
        try:
            from sfrfr.security.integrations import PRIVATE_STORAGE_BUCKET

            client.storage.from_(PRIVATE_STORAGE_BUCKET).remove([path])
        except Exception as exc:  # noqa: BLE001
            out["cleanup_storage_err"] = str(exc)[:120]
print(json.dumps({"cleanup": "done"}, ensure_ascii=False))
