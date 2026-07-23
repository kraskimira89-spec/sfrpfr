"""Render the landing-page implementation specification as a DOCX file."""

import re
from pathlib import Path

from docx import Document
from docx.shared import Cm, Pt


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "specs" / "10-landing-audit-and-implementation.md"
OUTPUT = ROOT / "docs" / "specs" / "10-landing-audit-and-implementation.docx"
ORDERED_ITEM_RE = re.compile(r"^\d+\.\s+(?P<text>.+)$")


def add_table(document: Document, rows: list[list[str]]) -> None:
    table = document.add_table(rows=0, cols=len(rows[0]))
    table.style = "Table Grid"
    for values in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, values, strict=True):
            cell.text = value


def ordered_item_text(line: str) -> str | None:
    """Return ordered-list content for any Markdown numeric prefix."""
    match = ORDERED_ITEM_RE.match(line)
    return match.group("text") if match else None


def main() -> None:
    document = Document()
    section = document.sections[0]
    section.top_margin = Cm(1.8)
    section.bottom_margin = Cm(1.8)
    section.left_margin = Cm(2)
    section.right_margin = Cm(2)

    style = document.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(10)

    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    in_code = False
    table_rows: list[list[str]] = []

    def flush_table() -> None:
        nonlocal table_rows
        if table_rows:
            add_table(document, table_rows)
            table_rows = []

    for line in lines:
        if line.startswith("```"):
            flush_table()
            in_code = not in_code
            continue

        if in_code:
            paragraph = document.add_paragraph()
            paragraph.style = document.styles["Normal"]
            run = paragraph.add_run(line)
            run.font.name = "Courier New"
            run.font.size = Pt(8)
            continue

        if line.startswith("|") and line.endswith("|"):
            parts = [item.strip() for item in line.strip("|").split("|")]
            if all(set(item) <= {"-", ":", " "} for item in parts):
                continue
            table_rows.append(parts)
            continue

        flush_table()

        if not line:
            continue
        if line.startswith("# "):
            document.add_heading(line[2:], level=0)
        elif line.startswith("## "):
            document.add_heading(line[3:], level=1)
        elif line.startswith("### "):
            document.add_heading(line[4:], level=2)
        elif line.startswith("- "):
            document.add_paragraph(line[2:], style="List Bullet")
        elif ordered_text := ordered_item_text(line):
            document.add_paragraph(ordered_text, style="List Number")
        elif line.startswith("**") and line.endswith("**"):
            document.add_paragraph(line.strip("*"))
        else:
            document.add_paragraph(line.replace("**", "").replace("`", ""))

    flush_table()
    document.add_page_break()
    document.add_paragraph("Конец документа")
    document.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
