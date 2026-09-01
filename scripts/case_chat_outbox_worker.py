#!/usr/bin/env python3
"""Запуск worker-а доставки общего чата в MAX."""

from __future__ import annotations

import argparse
import logging
import time

from sfrfr.core.config import get_settings
from sfrfr.services.case_chat_bot_jobs import process_bot_pipeline
from sfrfr.services.case_chat_delivery import process_pending_outbox

logger = logging.getLogger("sfrfr.case_chat_outbox_worker")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="обработать одну пачку и завершиться")
    args = parser.parse_args()
    settings = get_settings()
    poll_seconds = max(1.0, settings.case_chat_outbox_poll_seconds)

    while True:
        try:
            process_bot_pipeline(limit=20)
            process_pending_outbox(limit=20)
        except Exception:  # noqa: BLE001 — worker должен переживать временный сбой API/БД
            logger.exception("case chat pipeline batch failed")
        if args.once:
            return
        time.sleep(poll_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
