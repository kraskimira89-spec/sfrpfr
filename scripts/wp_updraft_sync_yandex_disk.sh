#!/usr/bin/env bash
# Синхронизация бэкапов UpdraftPlus → Яндекс.Диск (disk:/SFRFR-ops/wp-backups).
#
# Бесплатный UpdraftPlus не поддерживает Яндекс.Диск / WebDAV (это Premium).
# Этот скрипт грузит архивы из wp-content/updraft через Disk API (OAuth из /opt/sfrfr/.env).
# Только ops-папка SFRFR-ops; без ПДн-сканов дел.
#
#   bash /opt/sfrfr/scripts/wp_updraft_sync_yandex_disk.sh
# Cron (пн 04:30, после недельного Updraft):
#   30 4 * * 1 root APP_DIR=/opt/sfrfr bash /opt/sfrfr/scripts/wp_updraft_sync_yandex_disk.sh >>/var/log/sfrfr-wp-updraft-yadisk.log 2>&1
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/sfrfr}"
SITE_DIR="${SITE_DIR:-/var/www/taxi-doroga-dobra}"
UPDRAFT_DIR="${SITE_DIR}/wp-content/updraft"
ENV_FILE="${APP_DIR}/.env"
REMOTE_FOLDER="disk:/SFRFR-ops/wp-backups"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERR: no $ENV_FILE" >&2
  exit 1
fi

TOKEN="$(grep -m1 '^YANDEX_OAUTH_ACCESS_TOKEN=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r' | sed 's/^"//;s/"$//')"
DISK_ON="$(grep -m1 '^YANDEX_DISK_ENABLED=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r' | tr '[:upper:]' '[:lower:]')"

if [[ "${DISK_ON}" != "true" && "${DISK_ON}" != "1" && "${DISK_ON}" != "yes" ]]; then
  echo "ERR: YANDEX_DISK_ENABLED is not true" >&2
  exit 1
fi
if [[ -z "$TOKEN" ]]; then
  echo "ERR: empty YANDEX_OAUTH_ACCESS_TOKEN" >&2
  exit 1
fi

export YANDEX_OAUTH_ACCESS_TOKEN="$TOKEN"
export SFRFR_UPDRAFT_DIR="$UPDRAFT_DIR"
export SFRFR_REMOTE_FOLDER="$REMOTE_FOLDER"

python3 <<'PY'
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote

import urllib.error
import urllib.request

TOKEN = os.environ["YANDEX_OAUTH_ACCESS_TOKEN"]
UPDRAFT = Path(os.environ["SFRFR_UPDRAFT_DIR"])
REMOTE = os.environ["SFRFR_REMOTE_FOLDER"].rstrip("/")
API = "https://cloud-api.yandex.net/v1/disk"


def req(
    method: str,
    url: str,
    data: bytes | None = None,
    headers: dict | None = None,
    timeout: int = 120,
):
    h = {"Authorization": f"OAuth {TOKEN}"}
    if headers:
        h.update(headers)
    request = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read() if exc.fp else b""


def ensure_folder(path: str) -> None:
    enc = quote(path, safe="")
    code, _ = req("GET", f"{API}/resources?path={enc}", timeout=60)
    if code == 200:
        return
    code, body = req("PUT", f"{API}/resources?path={enc}", timeout=60)
    if code not in (200, 201, 409):
        raise SystemExit(f"mkdir failed {path}: HTTP {code} {body[:200]!r}")


def upload(local: Path) -> None:
    remote = f"{REMOTE}/{local.name}"
    enc = quote(remote, safe="")
    code, body = req("GET", f"{API}/resources/upload?path={enc}&overwrite=true", timeout=60)
    if code >= 400:
        raise RuntimeError(f"href failed {local.name}: HTTP {code} {body[:200]!r}")
    import json

    href = (json.loads(body.decode("utf-8") or "{}") or {}).get("href")
    if not href:
        raise RuntimeError(f"no href for {local.name}")
    # крупные zip — длинный таймаут; не грузим весь файл в память повторно через read_bytes для >80MB
    size = local.stat().st_size
    with local.open("rb") as fh:
        data = fh.read()
    code, body = req(
        "PUT",
        href,
        data=data,
        headers={"Content-Type": "application/octet-stream"},
        timeout=max(600, size // 50_000 + 120),
    )
    if code not in (200, 201, 202):
        raise RuntimeError(f"upload failed {local.name}: HTTP {code} {body[:200]!r}")
    print(f"OK uploaded {local.name} ({size} bytes)")

ensure_folder("disk:/SFRFR-ops")
ensure_folder(REMOTE)

if not UPDRAFT.is_dir():
    raise SystemExit(f"no updraft dir: {UPDRAFT}")

skip = {"index.html", "web.config"}
files = sorted(
    [
        p
        for p in UPDRAFT.iterdir()
        if p.is_file()
        and p.name not in skip
        and p.suffix.lower() in {".zip", ".gz", ".txt", ".crypt"}
        and p.stat().st_size > 0
    ],
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)

# не гоняем гигабайты истории: последние 8 файлов
files = files[:8]
if not files:
    print("WARN: no updraft archives to sync (run a backup in UpdraftPlus first)")
    sys.exit(0)

ok = 0
failed = 0
for f in files:
    try:
        upload(f)
        ok += 1
    except Exception as exc:  # noqa: BLE001
        failed += 1
        print(f"FAIL {f.name}: {exc}", file=sys.stderr)

print(f"done remote={REMOTE} ok={ok} failed={failed}")
print("NOTE: free UpdraftPlus has no native Yandex Disk; cloud path = this script")
if failed and not ok:
    sys.exit(1)
PY
