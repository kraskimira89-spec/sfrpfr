#!/usr/bin/env python3
"""Обход Wordstat по регионам АЗРФ / Крайнего Севера / приравненных.

Лимит по умолчанию: 80 запросов/час (запас до квоты API ~100).
При 429 / исчерпании окна — ждёт и продолжает, пока матрица не заполнена.

Справочник: docs/marketing-sales/reports/wordstat-north-regions.json

Usage:
  python scripts/wordstat_fetch_north_regions.py --list
  python scripts/wordstat_fetch_north_regions.py --until-done
  python scripts/wordstat_fetch_north_regions.py --until-done --rph 80
  python scripts/wordstat_fetch_north_regions.py --phrases-only
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
MATRIX_LATEST = OUT_DIR / "wordstat-north-geo-matrix.csv"
REGION_RF = "225"
DEFAULT_RPH = 80


class HourlyQuota:
    """Скользящее окно: не больше `limit` успешных запросов за 3600 с."""

    def __init__(self, limit: int = DEFAULT_RPH) -> None:
        self.limit = max(1, limit)
        self._times: list[float] = []

    def _prune(self, now: float) -> None:
        self._times = [t for t in self._times if now - t < 3600.0]

    def used(self) -> int:
        self._prune(time.time())
        return len(self._times)

    def wait_slot(self) -> None:
        while True:
            now = time.time()
            self._prune(now)
            if len(self._times) < self.limit:
                return
            oldest = self._times[0]
            sleep_for = 3600.0 - (now - oldest) + 3.0
            sleep_for = max(5.0, sleep_for)
            print(
                f"  quota {self.used()}/{self.limit} per hour — sleep {int(sleep_for)}s "
                f"then continue...",
                flush=True,
            )
            time.sleep(sleep_for)

    def mark(self) -> None:
        self._times.append(time.time())


_QUOTA = HourlyQuota(DEFAULT_RPH)


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


def api_post(path: str, body: dict) -> dict:
    """Бесконечные ретраи на 429: ждём окно квоты и продолжаем."""
    key, folder = creds()
    payload = {**body, "folderId": folder}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    attempt = 0
    while True:
        attempt += 1
        _QUOTA.wait_slot()
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
                _QUOTA.mark()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            if e.code == 429:
                # Часовая квота API: ждём почти час и снова
                wait = min(3600, 300 + 120 * min(attempt, 20))
                print(
                    f"  rate limit 429 — sleep {wait}s (attempt {attempt}), then resume...",
                    flush=True,
                )
                time.sleep(wait)
                continue
            raise SystemExit(f"Wordstat HTTP {e.code}: {err[:800]}") from e
        except (TimeoutError, urllib.error.URLError) as e:
            wait = min(300, 15 * min(attempt, 10))
            print(f"  network/timeout: {e!s}; sleep {wait}s...", flush=True)
            time.sleep(wait)


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


def cell_empty(row: dict, key: str) -> bool:
    return (row.get(key) or "").strip() in ("", "TBD")


def load_matrix_rows(path: Path) -> tuple[list[str], dict[str, dict]]:
    if not path.is_file():
        return [], {}
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        rows: dict[str, dict] = {}
        for row in reader:
            ph = (row.get("phrase") or "").strip()
            if ph:
                rows[ph] = dict(row)
    return fields, rows


def merge_matrix_sources() -> tuple[list[str], dict[str, dict]]:
    """Resume: latest + dated today's file (если есть)."""
    fields, rows = load_matrix_rows(MATRIX_LATEST)
    dated = OUT_DIR / f"wordstat-north-geo-matrix-{date.today().isoformat()}.csv"
    if dated.is_file() and dated.resolve() != MATRIX_LATEST.resolve():
        f2, r2 = load_matrix_rows(dated)
        for code in f2:
            if code not in fields:
                fields.append(code)
        for ph, row in r2.items():
            base = rows.get(ph) or {"phrase": ph}
            for k, v in row.items():
                if k == "phrase":
                    continue
                if cell_empty(base, k) and str(v or "").strip() not in ("", "TBD"):
                    base[k] = v
                elif k not in base or cell_empty(base, k):
                    base[k] = v
            rows[ph] = base
    return fields, rows


def count_missing(
    phrases: list[str],
    regions: list[dict],
    rows_by_phrase: dict[str, dict],
) -> tuple[int, int]:
    miss_rf = 0
    miss_geo = 0
    for phrase in phrases:
        row = rows_by_phrase.get(phrase) or {}
        if cell_empty(row, "freq_rf"):
            miss_rf += 1
        for reg in regions:
            if cell_empty(row, str(reg["code"])):
                miss_geo += 1
    return miss_rf, miss_geo


def cmd_list(catalog: dict) -> int:
    print("=== AZRF ===")
    for s in catalog["buckets"]["arctic_zone"]["subjects"]:
        print(f"  {s['name']}: id={s.get('wordstat_id')} coverage={s['coverage']}")
    print("=== Far North subjects ===")
    for s in catalog["buckets"]["far_north"]["subjects"]:
        print(f"  {s['name']}: id={s.get('wordstat_id')} coverage={s['coverage']}")
    print("=== Equated subjects ===")
    for s in catalog["buckets"]["equated"]["subjects"]:
        print(f"  {s['name']}: id={s.get('wordstat_id')} coverage={s['coverage']}")
    print("=== Crawl priority (with ID) ===")
    for s in unique_crawl_regions(catalog):
        print(f"  {s['code']} {s['name']} {s['wordstat_id']} - {s.get('reason', '')}")
    return 0


def cmd_phrases_rf(catalog: dict, *, limit: int | None) -> Path:
    phrases = list(catalog.get("pensioner_seed_phrases") or [])
    if limit is not None:
        phrases = phrases[:limit]
    rows: list[dict] = []
    for phrase in phrases:
        print(f"> RF {phrase}", flush=True)
        data = top_requests(phrase, REGION_RF, num=25)
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
        print(f"  RF={freq} (quota {_QUOTA.used()}/{_QUOTA.limit})", flush=True)
    out = OUT_DIR / f"wordstat-north-phrases-rf-{date.today().isoformat()}.csv"
    write_csv(out, ["phrase", "freq_rf", "similar_top"], rows)
    print(f"OK {out}")
    return out


def cmd_matrix(
    catalog: dict,
    *,
    limit_regions: int | None,
    limit_phrases: int | None,
    offset_phrases: int,
    region_code: str,
    only_phrase: str,
    until_done: bool,
) -> Path:
    regions = unique_crawl_regions(catalog)
    if region_code:
        regions = [r for r in regions if r.get("code") == region_code]
    if limit_regions is not None:
        regions = regions[:limit_regions]

    phrases = list(catalog.get("pensioner_seed_phrases") or [])
    if only_phrase.strip():
        phrases = [only_phrase.strip()]
    else:
        if offset_phrases:
            phrases = phrases[offset_phrases:]
        if limit_phrases is not None:
            phrases = phrases[:limit_phrases]

    region_codes = [str(r["code"]) for r in regions]
    existing_fields, rows_by_phrase = merge_matrix_sources()

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
        for ph, row in rows_by_phrase.items():
            if ph not in phrases:
                ordered.append(row)
        write_csv(MATRIX_LATEST, fieldnames, ordered)
        dated = OUT_DIR / f"wordstat-north-geo-matrix-{date.today().isoformat()}.csv"
        write_csv(dated, fieldnames, ordered)

    miss_rf, miss_geo = count_missing(phrases, regions, rows_by_phrase)
    print(
        f"Plan: phrases={len(phrases)} regions={len(regions)}; "
        f"missing RF={miss_rf} geo={miss_geo}; rph={_QUOTA.limit}",
        flush=True,
    )
    if miss_rf + miss_geo == 0 and until_done:
        print(f"Already complete: {MATRIX_LATEST}", flush=True)
        return MATRIX_LATEST

    round_no = 0
    total_new = 0
    while True:
        round_no += 1
        pending_geo = 0
        pending_rf = 0
        for phrase in phrases:
            row = rows_by_phrase.get(phrase) or {"phrase": phrase}
            if cell_empty(row, "freq_rf"):
                print(f"> RF {phrase}", flush=True)
                rf = top_requests(phrase, REGION_RF, num=15)
                row["freq_rf"] = str(exact_or_total(phrase, rf))
                similar = []
                for item in (rf.get("results") or [])[:8]:
                    if isinstance(item, dict) and item.get("phrase"):
                        similar.append(f"{item['phrase']}:{as_int(item.get('count'))}")
                row["similar_rf"] = " | ".join(similar)
                print(
                    f"  RF={row['freq_rf']} (quota {_QUOTA.used()}/{_QUOTA.limit})",
                    flush=True,
                )
                pending_rf += 1
                rows_by_phrase[phrase] = row
                persist()
            for reg in regions:
                code = str(reg["code"])
                if not cell_empty(row, code):
                    continue
                rid = str(reg["wordstat_id"])
                print(f"  > {code}({rid}) {phrase}", flush=True)
                g = top_requests(phrase, rid, num=5)
                row[code] = str(exact_or_total(phrase, g))
                print(
                    f"    ={row[code]} (quota {_QUOTA.used()}/{_QUOTA.limit})",
                    flush=True,
                )
                pending_geo += 1
                rows_by_phrase[phrase] = row
                persist()
            rows_by_phrase[phrase] = row
            persist()

        total_new += pending_rf + pending_geo
        miss_rf, miss_geo = count_missing(phrases, regions, rows_by_phrase)
        print(
            f"Round {round_no}: +RF={pending_rf} +geo={pending_geo}; "
            f"left RF={miss_rf} geo={miss_geo}",
            flush=True,
        )
        if miss_rf + miss_geo == 0:
            break
        if not until_done:
            break
        # На всякий случай: если за круг ничего не сняли — ждём час
        if pending_rf + pending_geo == 0:
            print("  no progress this round — sleep 3600s...", flush=True)
            time.sleep(3600)

    persist()
    print(
        f"OK {MATRIX_LATEST} (new cells ~ {total_new}; left RF={miss_rf} geo={miss_geo})",
        flush=True,
    )
    return MATRIX_LATEST


def main() -> int:
    global _QUOTA
    load_dotenv()
    catalog = load_catalog()
    p = argparse.ArgumentParser(description="Wordstat обход АЗРФ / КС / приравненных")
    p.add_argument("--list", action="store_true", help="Показать справочник регионов")
    p.add_argument("--phrases-only", action="store_true", help="Только РФ по seed-фразам")
    p.add_argument("--limit", type=int, default=None, help="Лимит фраз для --phrases-only")
    p.add_argument("--limit-regions", type=int, default=None)
    p.add_argument("--limit-phrases", type=int, default=None)
    p.add_argument("--offset-phrases", type=int, default=0, help="Пропустить первые N seed-фраз")
    p.add_argument("--region-code", type=str, default="", help="Один code из crawl_priority")
    p.add_argument("--phrase", type=str, default="")
    p.add_argument(
        "--rph",
        type=int,
        default=DEFAULT_RPH,
        help=f"Макс. запросов в час (default {DEFAULT_RPH}, квота API ~100)",
    )
    p.add_argument(
        "--until-done",
        action="store_true",
        default=True,
        help="Крутить раунды пока все ячейки не заполнены (по умолчанию вкл.)",
    )
    p.add_argument(
        "--once",
        action="store_true",
        help="Один проход без ожидания полного заполнения",
    )
    # legacy no-op keep for старых вызовов
    p.add_argument("--sleep", type=float, default=0.0, help=argparse.SUPPRESS)
    args = p.parse_args()

    _QUOTA = HourlyQuota(args.rph)
    until_done = bool(args.until_done) and not bool(args.once)

    if args.list:
        return cmd_list(catalog)
    if args.phrases_only:
        cmd_phrases_rf(catalog, limit=args.limit)
        return 0
    cmd_matrix(
        catalog,
        limit_regions=args.limit_regions,
        limit_phrases=args.limit_phrases,
        offset_phrases=args.offset_phrases,
        region_code=args.region_code,
        only_phrase=args.phrase,
        until_done=until_done,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
