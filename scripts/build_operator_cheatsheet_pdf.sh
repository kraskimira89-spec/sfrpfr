#!/usr/bin/env bash
# Сборка PDF шпаргалки оператора из Markdown (pandoc).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MD="$ROOT/docs/AMO/playbook-operator-new-lead-cheatsheet.md"
OUT="$ROOT/docs/AMO/assets/playbook-operator-new-lead-cheatsheet.pdf"
mkdir -p "$(dirname "$OUT")"

if ! command -v pandoc >/dev/null 2>&1; then
  echo "pandoc not found; install pandoc to build PDF" >&2
  exit 1
fi

# HTML → PDF через wkhtmltopdf (кириллица на Windows/Linux без TeX).
HTML="$(mktemp --suffix=.html 2>/dev/null || mktemp)"
trap 'rm -f "$HTML"' EXIT

pandoc "$MD" -o "$HTML" --standalone -V lang=ru \
  -c "data:text/css,body{font-family:Segoe UI,Arial,sans-serif;max-width:720px;margin:2em auto;line-height:1.4;font-size:11pt} table{border-collapse:collapse;width:100%} th,td{border:1px solid #ccc;padding:4px 8px} code,pre{background:#f4f4f4}"

if command -v wkhtmltopdf >/dev/null 2>&1; then
  wkhtmltopdf -q -B 10 -L 12 -R 12 -T 12 "$HTML" "$OUT"
elif command -v pandoc >/dev/null 2>&1 && pandoc --list-output-formats | grep -q pdf; then
  pandoc "$MD" -o "$OUT" -V geometry:margin=1.5cm -V lang=ru 2>/dev/null || {
    echo "PDF engine missing; wrote HTML only: $HTML" >&2
    cp "$HTML" "${OUT%.pdf}.html"
    exit 0
  }
else
  cp "$HTML" "${OUT%.pdf}.html"
  echo "wkhtmltopdf not found; wrote ${OUT%.pdf}.html" >&2
  exit 0
fi

echo "Wrote $OUT"
