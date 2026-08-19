"""Вывести тексты шаблонов задач amo для Digital Pipeline / копирования в UI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sfrfr.integrations.amocrm.task_templates import (  # noqa: E402
    AMO_TASK_TEMPLATES,
    OPERATOR_NOTE_TEMPLATE,
)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Шаблоны задач amoCRM (тексты для UI)")
    parser.add_argument(
        "--key",
        help="Ключ шаблона: first_contact, qualification, diag_offer, …",
    )
    parser.add_argument("--json", action="store_true", help="JSON вместо текста")
    parser.add_argument("--note", action="store_true", help="Шаблон заметки оператора")
    args = parser.parse_args()

    if args.note:
        print(OPERATOR_NOTE_TEMPLATE)
        return

    if args.key:
        tpl = AMO_TASK_TEMPLATES.get(args.key)
        if not tpl:
            keys = ", ".join(sorted(AMO_TASK_TEMPLATES))
            raise SystemExit(f"Unknown key {args.key!r}. Available: {keys}")
        if args.json:
            print(json.dumps(tpl, ensure_ascii=False, indent=2))
        else:
            print(f"# {tpl['title']}")
            print(f"# trigger: {tpl['trigger']}")
            print(f"# complete_till: {tpl['complete_till']}")
            print(f"# task_type_id: {tpl['task_type_id']}")
            print()
            print(tpl["text"])
        return

    if args.json:
        print(json.dumps(AMO_TASK_TEMPLATES, ensure_ascii=False, indent=2))
        return

    for key, tpl in AMO_TASK_TEMPLATES.items():
        print(f"=== {key} — {tpl['title']} ===")
        print(f"trigger: {tpl['trigger']}")
        print(f"complete_till: {tpl['complete_till']}")
        print(tpl["text"])
        print()


if __name__ == "__main__":
    main()
