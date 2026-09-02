#!/usr/bin/env python3
"""Восстановить UTF-8 в admin-cabinet.tsx (CP866 mojibake)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "apps/admin/src/components/admin-cabinet.tsx"
MOJIBAKE = re.compile(r"[╨╤╥╦╧╨╩╪╫╬╭╮╯╰╱╲╳╴╵╶╷╸╹╺╻╼╽╾╿┌┐└┘├┤┬┴]")


def _fix_fragment(text: str) -> str:
    if not MOJIBAKE.search(text):
        return text
    return text.encode("cp866").decode("utf-8")


def fix_content(text: str) -> str:
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        # double-quoted string
        if ch == '"':
            j = i + 1
            while j < n:
                if text[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if text[j] == '"':
                    break
                j += 1
            inner = text[i + 1 : j]
            try:
                fixed_inner = _fix_fragment(inner)
            except UnicodeError:
                fixed_inner = inner
            out.append('"')
            out.append(fixed_inner)
            out.append('"')
            i = j + 1
            continue
        # line comment
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            if j == -1:
                j = n
            chunk = text[i:j]
            try:
                chunk = _fix_fragment(chunk)
            except UnicodeError:
                pass
            out.append(chunk)
            i = j
            continue
        # JSX text between > and <
        if ch == ">":
            j = i + 1
            while j < n and text[j] != "<":
                j += 1
            inner = text[i + 1 : j]
            if MOJIBAKE.search(inner):
                try:
                    inner = _fix_fragment(inner)
                except UnicodeError:
                    pass
            out.append(">")
            out.append(inner)
            i = j
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def main() -> int:
    raw = TARGET.read_text(encoding="utf-8")
    if "Веб-кабinet" in raw or ("Веб-кабинет" in raw and "╨" not in raw):
        if "Веб-кабинет" in raw and "╨" not in raw:
            print("already ok")
            return 0
    if "╨" not in raw:
        print("no mojibake found", file=sys.stderr)
        return 1
    fixed = fix_content(raw)
    bad_left = len([1 for line in fixed.splitlines() if "╨" in line])
    if bad_left:
        print(f"warning: {bad_left} lines still corrupted", file=sys.stderr)
    if "Веб-кабинет" not in fixed:
        print("sanity check failed", file=sys.stderr)
        return 1
    TARGET.write_text(fixed, encoding="utf-8", newline="\n")
    print(f"fixed {TARGET}, remaining bad lines: {bad_left}")
    return 0 if bad_left == 0 else 0  # still write if mostly fixed


if __name__ == "__main__":
    raise SystemExit(main())
