"""Сборка PDF результата диагностики из заполненного Markdown.

Пример:
  python scripts/build_diagnosis_report_pdf.py scripts/assets/templates/diagnosis-stazh-report.example.md
  python scripts/build_diagnosis_report_pdf.py path/to/filled.md -o out/diag.pdf
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MD = ROOT / "scripts" / "assets" / "templates" / "diagnosis-stazh-report.md"
OUT_DIR = ROOT / "scripts" / "assets" / "templates" / "out"


def _edge_path() -> Path | None:
    for candidate in (
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft/Edge/Application/msedge.exe",
    ):
        if candidate.is_file():
            return candidate
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF диагностики из Markdown")
    parser.add_argument(
        "markdown",
        nargs="?",
        type=Path,
        default=DEFAULT_MD,
        help="Заполненный .md (по умолчанию пустой шаблон)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Путь к .pdf (по умолчанию templates/out/<stem>.pdf)",
    )
    args = parser.parse_args()

    md = args.markdown if args.markdown.is_absolute() else (ROOT / args.markdown)
    if not md.is_file():
        raise SystemExit(f"Файл не найден: {md}")

    if not shutil.which("pandoc"):
        raise SystemExit("pandoc not found — установите pandoc для сборки PDF")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = md.stem
    html = OUT_DIR / f"{stem}.html"
    pdf = args.output if args.output is not None else OUT_DIR / f"{stem}.pdf"
    if not pdf.is_absolute():
        pdf = ROOT / pdf
    pdf.parent.mkdir(parents=True, exist_ok=True)

    css = (
        "body{font-family:Segoe UI,Arial,sans-serif;max-width:720px;margin:1.5em auto;"
        "line-height:1.35;font-size:10.5pt;color:#111}"
        "h1{font-size:1.35rem;margin-bottom:0.35em}"
        "h2{font-size:1.1rem;margin-top:1.4em;border-bottom:1px solid #ddd;padding-bottom:0.2em}"
        "h3{font-size:1rem}"
        "table{border-collapse:collapse;width:100%;font-size:9.5pt;margin:0.8em 0}"
        "th,td{border:1px solid #bbb;padding:4px 6px;vertical-align:top}"
        "th{background:#f3f3f3}"
        "blockquote{border-left:3px solid #888;margin:0.8em 0;padding:0.2em 0.8em;color:#333}"
        "ul,ol{margin:0.4em 0 0.4em 1.2em}"
        "@media print{body{margin:0;max-width:none}}"
    )

    subprocess.run(
        [
            "pandoc",
            str(md),
            "-o",
            str(html),
            "--standalone",
            "-V",
            "lang=ru",
            "-c",
            f"data:text/css,{css}",
        ],
        check=True,
    )

    if shutil.which("wkhtmltopdf"):
        subprocess.run(
            ["wkhtmltopdf", "-q", "-B", "12", "-L", "14", "-R", "14", "-T", "12", str(html), str(pdf)],
            check=True,
        )
        print(f"Wrote {pdf}")
        return

    edge = _edge_path()
    if edge:
        uri = html.resolve().as_uri()
        subprocess.run(
            [
                str(edge),
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={pdf}",
                uri,
            ],
            check=True,
            capture_output=True,
        )
        if pdf.is_file():
            print(f"Wrote {pdf}")
            return

    print(f"Wrote {html} (откройте в браузере → Печать → PDF)", file=sys.stderr)


if __name__ == "__main__":
    main()
