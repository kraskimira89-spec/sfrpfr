#!/usr/bin/env python3
"""Запуск одного worker-а очереди document_ingest_jobs."""

from __future__ import annotations

import argparse

from sfrfr.core.config import get_settings
from sfrfr.services.document_ingest_worker import run_worker


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="обработать максимум один job")
    args = parser.parse_args()
    settings = get_settings()
    run_worker(once=args.once, poll_seconds=settings.document_worker_poll_seconds)


if __name__ == "__main__":
    main()
