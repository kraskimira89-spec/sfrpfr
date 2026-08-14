#!/usr/bin/env python3
"""Обход Wordstat по регионам АЗРФ / Крайнего Севера / приравненных.

Справочник: docs/marketing-sales/reports/wordstat-north-regions.json

Usage:
  python scripts/wordstat_fetch_north_regions.py --list
  python scripts/wordstat_fetch_north_regions.py --phrases-only
  python scripts/wordstat_fetch_north_regions.py --limit-regions 8 --limit-phrases 5
  python scripts/wordstat_fetch_north_regions.py --region-code yamal --phrase "северный стаж"
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
REGIONS_JSON = ROOT / "docs/marketing-sales/reports/wordstat-north-regions.json"
OUT_DIR = ROOT / "docs/marketing-sales/reports"
REGION_RF = "225"


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
            "Нужны YANDEX_WORDSTAT_API_KEY + YANDEX_FOLDER_ID (secrets/wordstat.env)"
        )
    return key, folder


def api_post(path: str, body: dict, *, retries: int = 10) -> dict:
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
                # часовая квота ~100: после серии коротких пауз ждём длиннее
                if attempt < 4:
                    wait = 20 * (attempt + 1)
                else:
                    wait = min(900, 180 * (attempt - 3))
                print(f"  rate limit, sleep {wait}s (attempt {attempt + 1}/{retries})...", flush=True)
                time.sleep(wait)
                continue
            raise SystemExit(last_err) from e
    raise SystemExit(last_err or "Wordstat failed")


def as_int(value: object) -> int:
    if value is None:
        return 0
    try:
        return int(str(value).replace(" ", "").replace("\u00a0", ""))
    except ValueError:
        return 0


def top_requests(phrase: str, region: str | None, num: int = 20) -> dict:
    body: dict = {
        "phrase": phrase,
        "numPhrases": num,
        "devices": ["DEVICE_ALL"],
    }
    if region:
        body["regions"] = [str(region)]
    return api_post("/topRequests", body)


def exact_or_total(phrase: str, data: dict) -> int:
    needle = phrase.strip().casefold()
    for row in data.get("results") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("phrase", "")).strip().casefold() == needle:
            return as_int(row.get("count"))
    return as_int(data.get("totalCount"))


def load_catalog() -> dict:
    return json.loads(REGIONS_JSON.read_text(encoding="utf-8"))


def unique_crawl_regions(catalog: dict) -> list[dict]:
    seen: set[int] = set()
    out: list[dict] = []
    for item in catalog.get("wordstat_crawl_priority") or []:
        rid = item.get("wordstat_id")
        if rid is None:
            continue
        rid_i = int(rid)
        if rid_i in seen:
            continue
        seen.add(rid_i)
        out.append(item)
    return out


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def cmd_list(catalog: dict) -> int:
    print("=== АЗРФ ===")
    for s in catalog["buckets"]["arctic_zone"]["subjects"]:
        print(f"  {s['name']}: id={s.get('wordstat_id')} coverage={s['coverage']}")
    print("=== Крайний Север (субъекты) ===")
    for s in catalog["buckets"]["far_north"]["subjects"]:
        print(f"  {s['name']}: id={s.get('wordstat_id')} coverage={s['coverage']}")
    print("=== Приравненные (субъекты) ===")
    for s in catalog["buckets"]["equated"]["subjects"]:
        print(f"  {s['name']}: id={s.get('wordstat_id')} coverage={s['coverage']}")
    print("=== Crawl priority (с ID) ===")
    for s in unique_crawl_regions(catalog):
        print(f"  {s['code']} {s['name']} {s['wordstat_id']} — {s.get('reason','')}")
    return 0


def cmd_phrases_rf(catalog: dict, *, sleep_s: float, limit: int | None) -> Path:
    phrases = list(catalog.get("pensioner_seed_phrases") or [])
    if limit is not None:
        phrases = phrases[:limit]
    rows: list[dict] = []
    for phrase in phrases:
        print(f"> RF {phrase}", flush=True)
        data = top_requests(phrase, REGION_RF, num=25)
        time.sleep(sleep_s)
        freq = exact_or_total(phrase, data)
        similar = []
        for row in (data.get("results") or [])[:10]:
            if isinstance(row, dict) and row.get("phrase"):
                similar.append(f"{row['phrase']}:{as_int(row.get('count'))}")
        rows.append(
            {
                "phrase": phrase,
                "freq_rf": str(freq),
                "similar_top": " | ".join(similar),
            }
        )
        print(f"  RF={freq}", flush=True)
    out = OUT_DIR / f"wordstat-north-phrases-rf-{date.today().isoformat()}.csv"
    write_csv(out, ["phrase", "freq_rf", "similar_top"], rows)
    print(f"OK {out}")
    return out


def cmd_matrix(
    catalog: dict,
    *,
    sleep_s: float,
    limit_regions: int | None,
    limit_phrases: int | None,
    region_code: str,
    only_phrase: str,
) -> Path:
    regions = unique_crawl_regions(catalog)
    if region_code:
        regions = [r for r in regions if r.get("code") == region_code]
    if limit_regions is not None:
        regions = regions[:limit_regions]

    phrases = list(catalog.get("pensioner_seed_phrases") or [])
    if only_phrase.strip():
        phrases = [only_phrase.strip()]
    elif limit_phrases is not None:
        phrases = phrases[:limit_phrases]

    region_codes = [str(r["code"]) for r in regions]
    out = OUT_DIR / f"wordstat-north-geo-matrix-{date.today().isoformat()}.csv"
    rows_by_phrase: dict[str, dict] = {}
    existing_fields: list[str] = []
    if out.is_file():
        with out.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            existing_fields = list(reader.fieldnames or [])
            for row in reader:
                ph = (row.get("phrase") or "").strip()
                if ph:
                    rows_by_phrase[ph] = dict(row)

    # Не теряем уже снятые колонки при расширении списка субъектов
    fieldnames: list[str] = ["phrase", "freq_rf"]
    for code in existing_fields:
        if code in ("phrase", "freq_rf", "similar_rf"):
            continue
        if code not in fieldnames:
            fieldnames.append(code)
    for code in region_codes:
        if code not in fieldnames:
            fieldnames.append(code)
    if "similar_rf" not in fieldnames:
        fieldnames.append("similar_rf")

    def persist() -> None:
        ordered = [rows_by_phrase[p] for p in phrases if p in rows_by_phrase]
        # плюс старые фразы, которых нет в текущем списке
        for ph, row in rows_by_phrase.items():
            if ph not in phrases:
                ordered.append(row)
        write_csv(out, fieldnames, ordered)

    pending_geo = 0
    for phrase in phrases:
        row = rows_by_phrase.get(phrase) or {"phrase": phrase}
        if not (row.get("freq_rf") or "").strip():
            print(f"> RF {phrase}", flush=True)
            rf = top_requests(phrase, REGION_RF, num=15)
            time.sleep(sleep_s)
            row["freq_rf"] = str(exact_or_total(phrase, rf))
            similar = []
            for item in (rf.get("results") or [])[:8]:
                if isinstance(item, dict) and item.get("phrase"):
                    similar.append(f"{item['phrase']}:{as_int(item.get('count'))}")
            row["similar_rf"] = " | ".join(similar)
            print(f"  RF={row['freq_rf']}", flush=True)
            rows_by_phrase[phrase] = row
            persist()
        for reg in regions:
            code = str(reg["code"])
            if (row.get(code) or "").strip() not in ("", "TBD"):
                continue
            rid = str(reg["wordstat_id"])
            print(f"  > {code}({rid}) {phrase}", flush=True)
            g = top_requests(phrase, rid, num=5)
            time.sleep(sleep_s)
            row[code] = str(exact_or_total(phrase, g))
            print(f"    ={row[code]}", flush=True)
            pending_geo += 1
            rows_by_phrase[phrase] = row
            persist()
        rows_by_phrase[phrase] = row
        persist()

    persist()
    print(f"OK {out} (new geo cells this run ≈ {pending_geo})")
    return out


def main() -> int:
    load_dotenv()
    catalog = load_catalog()
    p = argparse.ArgumentParser(description="Wordstat обход АЗРФ / КС / приравненных")
    p.add_argument("--list", action="store_true", help="Показать справочник регионов")
    p.add_argument("--phrases-only", action="store_true", help="Только РФ по seed-фразам")
    p.add_argument("--limit", type=int, default=None, help="Лимит фраз для --phrases-only")
    p.add_argument("--limit-regions", type=int, default=None)
    p.add_argument("--limit-phrases", type=int, default=None)
    p.add_argument("--region-code", type=str, default="", help="Один code из crawl_priority")
    p.add_argument("--phrase", type=str, default="")
    p.add_argument("--sleep", type=float, default=0.4)
    args = p.parse_args()

    if args.list:
        return cmd_list(catalog)
    if args.phrases_only:
        cmd_phrases_rf(catalog, sleep_s=args.sleep, limit=args.limit)
        return 0
    cmd_matrix(
        catalog,
        sleep_s=args.sleep,
        limit_regions=args.limit_regions,
        limit_phrases=args.limit_phrases,
        region_code=args.region_code,
        only_phrase=args.phrase,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
