"""Доимпорт аварийного буфера заявок (storage/emergency_leads.jsonl) в БД.

По умолчанию dry-run (только счётчики). Запись — с флагом --apply, после восстановления БД:

    sudo -u sfrfr bash -lc 'cd /opt/sfrfr && set -a && . ./.env && set +a && \
      .venv/bin/python scripts/import_emergency_leads.py --apply'
"""

from __future__ import annotations

import argparse
import json

from sfrfr.services.lead_emergency_import import import_emergency_leads


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="записать в БД (иначе dry-run)")
    args = parser.parse_args()
    report = import_emergency_leads(apply=args.apply)
    print(json.dumps(report, ensure_ascii=False))
    return 1 if report.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
