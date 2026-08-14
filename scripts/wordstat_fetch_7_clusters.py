#!/usr/bin/env python3
"""Выгрузка частот Яндекс Wordstat (Search API v2) для CSV 7 кластеров.

Env (первый найденный файл, плюс .env):
  secrets/wordstat.env
  secrets/yandex-wordstat.env
  secrets/yandexAI_studio.env
  .env

Переменные:
  YANDEX_WORDSTAT_API_KEY / YANDEX_SEARCH_API_KEY / YANDEX_API_KEY
  YANDEX_WORDSTAT_FOLDER_ID или YANDEX_FOLDER_ID

Usage:
  python scripts/wordstat_fetch_7_clusters.py
  python scripts/wordstat_fetch_7_clusters.py --limit 3
  python scripts/wordstat_fetch_7_clusters.py --phrase "не учли стаж в ИЛС"
  python scripts/wordstat_fetch_7_clusters.py --no-geo
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "https://searchapi.api.cloud.yandex.net/v2/wordstat"
DEFAULT_CSV = ROOT / "docs/marketing-sales/reports/wordstat-7-clusters-template.csv"

# Регионы Wordstat (ID Яндекса)
REGION_RF = "225"
GEO_REGIONS: dict[str, str] = {
    "Москва": "213",
    "СПб": "2",
    "ЯНАО": "10842",
    "ХМАО": "11193",
}


def load_dotenv() -> None:
    for rel in (
        "secrets/wordstat.env",
        "secrets/yandex-wordstat.env",
        "secrets/yandexAI_studio.env",
        ".env",
    ):
        path = ROOT / rel
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip("\"'")
            if k and k not in os.environ:
                os.environ[k] = v


def creds() -> tuple[str, str]:
    key = (
        os.environ.get("YANDEX_WORDSTAT_API_KEY", "").strip()
        or os.environ.get("YANDEX_SEARCH_API_KEY", "").strip()
        or os.environ.get("YANDEX_API_KEY", "").strip()
    )
    folder = (
        os.environ.get("YANDEX_WORDSTAT_FOLDER_ID", "").strip()
        or os.environ.get("YANDEX_FOLDER_ID", "").strip()
    )
    if not key or not folder:
        raise SystemExit(
            "Нужны YANDEX_WORDSTAT_API_KEY (или YANDEX_SEARCH_API_KEY) + YANDEX_FOLDER_ID "
            "(secrets/wordstat.env или secrets/yandex-wordstat.env)"
        )
    return key, folder


def api_post(path: str, body: dict, *, retries: int = 6) -> dict:
    key, folder = creds()
    payload = {**body, "folderId": folder}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last_err = ""
    for attempt in range(retries):
        req = urllib.request.Request(
            f"{API}{path}",
            data=data,
            headers={
                "Authorization": f"Api-Key {key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            last_err = f"Wordstat HTTP {e.code}: {err[:800]}"
            if e.code == 429:
                wait = min(120, 15 * (attempt + 1))
                print(f"  rate limit, sleep {wait}s...", flush=True)
                time.sleep(wait)
                continue
            raise SystemExit(last_err) from e
    raise SystemExit(last_err or "Wordstat failed")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def as_int(value: object) -> int:
    if value is None:
        return 0
    try:
        return int(str(value).replace(" ", "").replace("\u00a0", ""))
    except ValueError:
        return 0


def top_requests(phrase: str, region: str | None, num: int = 30) -> dict:
    body: dict = {
        "phrase": phrase,
        "numPhrases": num,
        "devices": ["DEVICE_ALL"],
    }
    if region:
        body["regions"] = [str(region)]
    return api_post("/topRequests", body)


def exact_or_total(phrase: str, data: dict) -> int:
    """Частота самой фразы: exact match в results, иначе totalCount."""
    needle = phrase.strip().casefold()
    for row in data.get("results") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("phrase", "")).strip().casefold() == needle:
            return as_int(row.get("count"))
    return as_int(data.get("totalCount"))


def format_geo(parts: dict[str, int]) -> str:
    return "; ".join(f"{name}:{n}" for name, n in parts.items())


def fetch_phrase(phrase: str, *, with_geo: bool, sleep_s: float) -> tuple[int, str, list[str]]:
    rf = top_requests(phrase, REGION_RF)
    time.sleep(sleep_s)
    freq_rf = exact_or_total(phrase, rf)
    similar = []
    for row in (rf.get("results") or [])[:8]:
        if isinstance(row, dict) and row.get("phrase"):
            similar.append(f"{row['phrase']}:{as_int(row.get('count'))}")
    for row in (rf.get("associations") or [])[:5]:
        if isinstance(row, dict) and row.get("phrase"):
            similar.append(f"assoc:{row['phrase']}:{as_int(row.get('count'))}")

    geo_parts: dict[str, int] = {}
    if with_geo:
        for name, rid in GEO_REGIONS.items():
            g = top_requests(phrase, rid, num=5)
            time.sleep(sleep_s)
            geo_parts[name] = exact_or_total(phrase, g)
    return freq_rf, format_geo(geo_parts) if geo_parts else "", similar


def run_csv(
    csv_path: Path,
    *,
    limit: int | None,
    with_geo: bool,
    sleep_s: float,
    only_tbd: bool,
) -> Path:
    rows: list[dict[str, str]] = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            rows.append(dict(row))

    if "similar_top" not in fieldnames:
        fieldnames.append("similar_top")

    out = csv_path.with_name(f"wordstat-7-clusters-filled-{date.today().isoformat()}.csv")
    done = 0
    for row in rows:
        if limit is not None and done >= limit:
            break
        q = (row.get("query") or "").strip()
        if not q:
            continue
        if only_tbd and (row.get("freq_rf") or "").strip() not in ("", "TBD"):
            continue
        print(f"> {q}", flush=True)
        freq_rf, freq_geo, similar = fetch_phrase(q, with_geo=with_geo, sleep_s=sleep_s)
        row["freq_rf"] = str(freq_rf)
        if with_geo:
            row["freq_geo"] = freq_geo or row.get("freq_geo", "")
        row["similar_top"] = " | ".join(similar)
        done += 1
        print(f"  RF={freq_rf} geo={row.get('freq_geo', '')[:80]}", flush=True)
        # Инкрементально — чтобы 429 не терял прогресс
        write_csv(csv_path, fieldnames, rows)
        write_csv(out, fieldnames, rows)

    print(f"OK wrote {out} and updated {csv_path} ({done} phrases)")
    return out


def main() -> int:
    load_dotenv()
    p = argparse.ArgumentParser(description="Wordstat Search API → CSV 7 кластеров")
    p.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    p.add_argument("--limit", type=int, default=None, help="Сколько фраз обработать")
    p.add_argument("--phrase", type=str, default="", help="Одна фраза (smoke-test)")
    p.add_argument("--no-geo", action="store_true", help="Только РФ, без гео-срезов")
    p.add_argument("--sleep", type=float, default=0.35, help="Пауза между запросами")
    p.add_argument(
        "--all",
        action="store_true",
        help="Перезаписать даже заполненные freq_rf (по умолчанию только TBD)",
    )
    args = p.parse_args()
    with_geo = not args.no_geo

    if args.phrase.strip():
        freq_rf, freq_geo, similar = fetch_phrase(
            args.phrase.strip(), with_geo=with_geo, sleep_s=args.sleep
        )
        print(json.dumps(
            {"phrase": args.phrase.strip(), "freq_rf": freq_rf, "freq_geo": freq_geo, "similar": similar},
            ensure_ascii=False,
            indent=2,
        ))
        return 0

    if not args.csv.is_file():
        raise SystemExit(f"CSV not found: {args.csv}")
    run_csv(
        args.csv,
        limit=args.limit,
        with_geo=with_geo,
        sleep_s=args.sleep,
        only_tbd=not args.all,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
