"""Inspect one case: Disk + Storage + documents."""
from __future__ import annotations

import httpx

from sfrfr.db.session import get_supabase_client
from sfrfr.integrations.yandex_workspace.oauth import oauth_headers
from sfrfr.security.integrations import PRIVATE_STORAGE_BUCKET

CID = "62310d24-5699-441e-8553-8964685c8276"


def list_disk(path: str) -> None:
    with httpx.Client(timeout=30.0) as http:
        r = http.get(
            "https://cloud-api.yandex.net/v1/disk/resources",
            params={"path": path, "limit": 100},
            headers=oauth_headers(),
        )
        print(f"DISK {path} -> {r.status_code}")
        if r.status_code >= 400:
            print((r.text or "")[:200])
            return
        body = r.json() if r.content else {}
        items = ((body.get("_embedded") or {}).get("items") or [])
        for it in items:
            print(
                f"  {it.get('type')}\t{it.get('name')}\t{it.get('size')}\t{it.get('mime_type')}"
            )
            if it.get("type") == "dir":
                list_disk(it.get("path") or f"{path}/{it.get('name')}")


def main() -> None:
    list_disk(f"disk:/SFRFR-cases/{CID}")
    client = get_supabase_client()
    try:
        docs = (
            client.table("documents")
            .select("id,storage_path,doc_type,created_at")
            .eq("case_id", CID)
            .execute()
            .data
            or []
        )
        print(f"DOCS={len(docs)}")
        for d in docs:
            print(d)
    except Exception as exc:  # noqa: BLE001
        print(f"DOCS_ERR={type(exc).__name__}:{exc}")

    bucket = PRIVATE_STORAGE_BUCKET
    for prefix in (
        CID,
        f"quarantine/{CID}",
        f"verified/{CID}",
        f"ingest/{CID}",
    ):
        try:
            items = client.storage.from_(bucket).list(prefix) or []
            print(f"STORAGE {prefix} -> {len(items)}")
            for it in items[:30]:
                print(" ", it)
        except Exception as exc:  # noqa: BLE001
            print(f"STORAGE_ERR {prefix}: {type(exc).__name__}:{exc}")


if __name__ == "__main__":
    main()
