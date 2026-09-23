"""Find where real client uploads live for prod cases."""
from __future__ import annotations

from pathlib import Path

import httpx

from sfrfr.core.config import get_settings
from sfrfr.db.session import get_supabase_client
from sfrfr.integrations.yandex_workspace.oauth import oauth_headers
from sfrfr.security.integrations import PRIVATE_STORAGE_BUCKET


def main() -> None:
    settings = get_settings()
    local = Path(settings.storage_local_path)
    print(f"LOCAL_PATH={local} exists={local.exists()}")
    if local.exists():
        cases = [p for p in local.iterdir() if p.is_dir()]
        print(f"LOCAL_CASE_DIRS={len(cases)}")
        files = list(local.rglob("*"))
        file_only = [p for p in files if p.is_file()]
        print(f"LOCAL_FILES={len(file_only)}")
        by_suf: dict[str, int] = {}
        for p in file_only:
            by_suf[p.suffix.lower() or "(none)"] = by_suf.get(p.suffix.lower() or "(none)", 0) + 1
        for k, v in sorted(by_suf.items(), key=lambda x: -x[1])[:20]:
            print(f"LOCAL_SUF\t{k}\t{v}")
        # sample case matching uuid
        cid = "62310d24-5699-441e-8553-8964685c8276"
        cdir = local / cid
        print(f"LOCAL_CASE_EXISTS={cdir.exists()}")
        if cdir.exists():
            for p in sorted(cdir.rglob("*")):
                if p.is_file():
                    print(f"  {p.relative_to(local)}\t{p.stat().st_size}")

    client = get_supabase_client()
    # total documents via count
    try:
        r = client.table("documents").select("id", count="exact").limit(1).execute()
        print(f"DOCUMENTS_REST_COUNT={r.count}")
    except Exception as exc:  # noqa: BLE001
        print(f"DOCUMENTS_ERR={exc}")

    # storage root listing
    try:
        roots = client.storage.from_(PRIVATE_STORAGE_BUCKET).list("") or []
        print(f"STORAGE_ROOT={len(roots)}")
        for it in roots[:30]:
            print(" ", it.get("name"), it.get("id"), it.get("metadata"))
    except Exception as exc:  # noqa: BLE001
        print(f"STORAGE_ERR={exc}")

    # Disk: count by extension across all case folders
    with httpx.Client(timeout=60.0) as http:
        r = http.get(
            "https://cloud-api.yandex.net/v1/disk/resources",
            params={"path": "disk:/SFRFR-cases", "limit": 100},
            headers=oauth_headers(),
        )
        items = (((r.json() or {}).get("_embedded") or {}).get("items") or [])
        dirs = [i for i in items if i.get("type") == "dir"]
        suf: dict[str, int] = {}
        total = 0
        for d in dirs:
            path = d.get("path")
            r2 = http.get(
                "https://cloud-api.yandex.net/v1/disk/resources",
                params={"path": path, "limit": 100},
                headers=oauth_headers(),
            )
            for it in (((r2.json() or {}).get("_embedded") or {}).get("items") or []):
                if it.get("type") != "file":
                    continue
                name = str(it.get("name") or "")
                ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else "(none)"
                suf[ext] = suf.get(ext, 0) + 1
                total += 1
        print(f"DISK_FILES_TOTAL={total}")
        for k, v in sorted(suf.items(), key=lambda x: -x[1]):
            print(f"DISK_SUF\t{k}\t{v}")


if __name__ == "__main__":
    main()
