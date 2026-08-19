"""Сборка PDF шпаргалки оператора (pandoc HTML + Edge/wkhtmltopdf)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MD = ROOT / "docs" / "AMO" / "playbook-operator-new-lead-cheatsheet.md"
OUT_DIR = ROOT / "docs" / "AMO" / "assets"
PDF = OUT_DIR / "playbook-operator-new-lead-cheatsheet.pdf"
HTML = OUT_DIR / "playbook-operator-new-lead-cheatsheet.html"


def _edge_path() -> Path | None:
    for candidate in (
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft/Edge/Application/msedge.exe",
    ):
        if candidate.is_file():
            return candidate
    return None


def main() -> None:
    if not shutil.which("pandoc"):
        raise SystemExit("pandoc not found — установите pandoc для сборки PDF")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    css = (
        "body{font-family:Segoe UI,Arial,sans-serif;max-width:720px;margin:2em auto;"
        "line-height:1.4;font-size:11pt}"
        "table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #ccc;padding:4px 8px}"
        "code,pre{background:#f4f4f4}"
    )

    subprocess.run(
        [
            "pandoc",
            str(MD),
            "-o",
            str(HTML),
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
            ["wkhtmltopdf", "-q", "-B", "10", "-L", "12", "-R", "12", "-T", "12", str(HTML), str(PDF)],
            check=True,
        )
        print(f"Wrote {PDF}")
        return

    edge = _edge_path()
    if edge:
        uri = HTML.resolve().as_uri()
        subprocess.run(
            [
                str(edge),
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={PDF}",
                uri,
            ],
            check=True,
            capture_output=True,
        )
        if PDF.is_file():
            print(f"Wrote {PDF}")
            return

    print(f"Wrote {HTML} (open in browser → Print → PDF)", file=sys.stderr)


if __name__ == "__main__":
    main()
