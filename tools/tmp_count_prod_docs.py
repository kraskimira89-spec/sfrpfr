"""Prod: accurate document counts (SQL + Storage + Disk)."""

from __future__ import annotations

import os
from collections import Counter
from urllib.parse import urlparse

import httpx

from sfrfr.db.session import get_supabase_client
from sfrfr.integrations.yandex_workspace.disk import CASES_FOLDER
from sfrfr.integrations.yandex_workspace.oauth import oauth_headers
from sfrfr.security.integrations import PRIVATE_STORAGE_BUCKET


def normalize_dsn(raw: str) -> str:
    url = (raw or "").strip()
    for prefix in ("postgresql+psycopg://", "postgresql+psycopg2://", "postgres+psycopg://"):
        if url.startswith(prefix):
            url = "postgresql://" + url[len(prefix) :]
            break
    return url


def sql_counts() -> None:
    raw = (os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL") or "").strip()
    dsn = normalize_dsn(raw)
    parsed = urlparse(dsn)
    print(f"SQL_HOST={parsed.hostname}:{parsed.port} DB={parsed.path.lstrip('/')}")
    import psycopg

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_name IN ('documents','cases')
                ORDER BY 1,2
                """
            )
            print("TABLES=" + str(cur.fetchall()))
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='documents'
                ORDER BY ordinal_position
                """
            )
            cols = [r[0] for r in cur.fetchall()]
            print("DOC_COLUMNS=" + ",".join(cols) if cols else "DOC_COLUMNS=(missing)")
            if not cols:
                return
            cur.execute("SELECT count(*) FROM public.documents")
            print(f"DOCUMENTS_TOTAL={cur.fetchone()[0]}")
            if "upload_source" in cols:
                cur.execute(
                    """
                    SELECT coalesce(upload_source,'(null)'), count(*)
                    FROM public.documents GROUP BY 1 ORDER BY 2 DESC
                    """
                )
                for a, b in cur.fetchall():
                    print(f"BY_SOURCE\t{a}\t{b}")
                cur.execute(
                    """
                    SELECT count(*) FROM public.documents
                    WHERE upload_source IN ('cabinet','max')
                    """
                )
                print(f"CLIENT_CABINET_MAX={cur.fetchone()[0]}")
            if "uploaded_by" in cols:
                cur.execute(
                    """
                    SELECT coalesce(uploaded_by::text,'(null)'), count(*)
                    FROM public.documents GROUP BY 1 ORDER BY 2 DESC
                    """
                )
                for a, b in cur.fetchall():
                    print(f"BY_UPLOADER\t{a}\t{b}")


def storage_count() -> None:
    client = get_supabase_client()
    bucket = PRIVATE_STORAGE_BUCKET
    files = 0
    case_dirs = 0

    def list_path(path: str) -> list:
        try:
            return client.storage.from_(bucket).list(path, {"limit": 100, "offset": 0}) or []
        except Exception:  # noqa: BLE001
            return []

    roots = list_path("")
    # also quarantine/verified prefixes
    queue = [""]
    seen: set[str] = set()
    while queue:
        path = queue.pop()
        if path in seen:
            continue
        seen.add(path)
        items = list_path(path)
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            if not name:
                continue
            full = f"{path}/{name}" if path else name
            # heuristically: folders have id/metadata without size sometimes
            meta = item.get("metadata")
            if meta is None and item.get("id") is None:
                # likely folder
                if path == "":
                    case_dirs += 1
                queue.append(full)
            else:
                files += 1
    print(f"STORAGE_CASE_DIRS_ROOT≈{case_dirs}")
    print(f"STORAGE_FILES≈{files}")
    print(f"STORAGE_BUCKET={bucket}")


def disk_count() -> None:
    with httpx.Client(timeout=60.0) as http:
        offset = 0
        dirs: list[dict] = []
        while True:
            resp = http.get(
                "https://cloud-api.yandex.net/v1/disk/resources",
                params={"path": CASES_FOLDER, "limit": 100, "offset": offset},
                headers=oauth_headers(),
            )
            body = resp.json() if resp.content else {}
            items = (body.get("_embedded") or {}).get("items") or []
            batch = [i for i in items if i.get("type") == "dir"]
            dirs.extend(batch)
            if len(items) < 100:
                break
            offset += 100

        files = 0
        by_sub: Counter[str] = Counter()
        for d in dirs:
            base = d.get("path") or f"{CASES_FOLDER}/{d.get('name')}"
            for sub in ("incoming", "outgoing", "chat", None):
                path = f"{base}/{sub}" if sub else base
                r2 = http.get(
                    "https://cloud-api.yandex.net/v1/disk/resources",
                    params={"path": path, "limit": 100},
                    headers=oauth_headers(),
                )
                if r2.status_code >= 400:
                    continue
                b2 = r2.json() if r2.content else {}
                for it in (b2.get("_embedded") or {}).get("items") or []:
                    if it.get("type") != "file":
                        continue
                    name = str(it.get("name") or "")
                    if name in {"meta.txt", "history.md"}:
                        continue
                    files += 1
                    by_sub[sub or "root"] += 1

        print(f"DISK_CASE_FOLDERS={len(dirs)}")
        print(f"DISK_CLIENT_FILES={files}")
        for k, v in sorted(by_sub.items()):
            print(f"DISK_SUB\t{k}\t{v}")
        print("DISK_WEB=https://disk.yandex.ru/client/disk/SFRFR-cases")


def main() -> None:
    try:
        sql_counts()
    except Exception as exc:  # noqa: BLE001
        print(f"SQL_ERROR={type(exc).__name__}:{exc}")
    try:
        storage_count()
    except Exception as exc:  # noqa: BLE001
        print(f"STORAGE_ERROR={type(exc).__name__}:{exc}")
    try:
        disk_count()
    except Exception as exc:  # noqa: BLE001
        print(f"DISK_ERROR={type(exc).__name__}:{exc}")


if __name__ == "__main__":
    main()
