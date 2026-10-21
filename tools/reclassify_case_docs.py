"""Повторная классификация документов дела без повторной загрузки клиентом.

Пример:
  .\\.venv\\Scripts\\python.exe tools/reclassify_case_docs.py --case-id <uuid>
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Reclassify untyped case documents")
    parser.add_argument("--case-id", required=True)
    parser.add_argument(
        "--settle-preview",
        action="store_true",
        help="Показать итоговое сообщение комплекта (без отправки)",
    )
    args = parser.parse_args()
    from sfrfr.integrations.max import document_background as bg

    n = bg.reclassify_case_untyped(args.case_id)
    print(f"reclassified={n} case={args.case_id[:8]}")
    if args.settle_preview:
        body, complete = bg.final_message_for_case(args.case_id)
        print("---")
        print(body)
        print("---")
        print(f"complete={complete}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
