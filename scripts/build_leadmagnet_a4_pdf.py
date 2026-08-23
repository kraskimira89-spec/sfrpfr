"""Сборка PDF лид-магнита A4 (1 стр.) из HTML через Edge/wkhtmltopdf.

Выход (канон рассылки):
  scripts/assets/leadmagnets/pension-checklist-a4-standard.pdf
  scripts/assets/leadmagnets/pension-checklist-a4-bw.pdf
  scripts/assets/leadmagnets/pension-checklist-a4-preview.png
"""

from __future__ import annotations

import base64
import io
import os
import shutil
import subprocess
import sys
from pathlib import Path

import segno

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "scripts" / "assets" / "leadmagnets"
HTML = OUT_DIR / "pension-checklist-a4-print.html"
LOGO = ROOT / "scripts" / "assets" / "sfrfr-logo-light.png"
QR_URL = "https://proverkastaza.ru/chek-list-dokumentov/"
PDF_STANDARD = OUT_DIR / "pension-checklist-a4-standard.pdf"
PDF_BW = OUT_DIR / "pension-checklist-a4-bw.pdf"
PNG_PREVIEW = OUT_DIR / "pension-checklist-a4-preview.png"


def _edge_path() -> Path | None:
    for candidate in (
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft/Edge/Application/msedge.exe",
    ):
        if candidate.is_file():
            return candidate
    return None


def _logo_data_uri() -> str:
    if not LOGO.is_file():
        return ""
    encoded = base64.b64encode(LOGO.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _qr_svg() -> str:
    qr = segno.make(QR_URL, error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=3, border=1, dark="#1b486c", light="#ffffff")
    return buf.getvalue().decode("utf-8")


def _html(*, grayscale: bool = False) -> str:
    logo = _logo_data_uri()
    logo_block = (
        f'<img class="a4-logo" src="{logo}" alt="Проверка стажа" width="120" height="32">'
        if logo
        else '<span class="a4-brand">Проверка стажа</span>'
    )
    bw = " bw" if grayscale else ""
    qr = _qr_svg()
    return f"""<!DOCTYPE html>
<html lang="ru" class="a4-root{bw}">
<head>
<meta charset="utf-8">
<title>Как собрать документы для проверки пенсионного стажа</title>
<style>
:root {{
  --a4-ink: #1f2933;
  --a4-navy: #1b486c;
  --a4-warn: #7a4d00;
  --a4-warn-bg: #fff8e8;
  --a4-soft: #eff6fb;
  --a4-line: #b7c6d2;
}}
* {{ box-sizing: border-box; }}
html, body {{
  margin: 0;
  padding: 0;
  color: var(--a4-ink);
  font-family: Arial, "PT Sans", "Noto Sans", sans-serif;
  font-size: 11.5pt;
  line-height: 1.38;
  background: #fff;
}}
html.bw, html.bw * {{
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}}
html.bw .a4-page {{
  filter: grayscale(100%);
}}
.a4-page {{
  width: 210mm;
  min-height: 297mm;
  padding: 14mm 16mm 12mm;
  margin: 0 auto;
}}
.a4-top {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding-bottom: 6px;
  margin-bottom: 8px;
  border-bottom: 1px solid var(--a4-line);
}}
.a4-logo {{ display: block; height: 28px; width: auto; }}
.a4-brand {{ font-weight: 700; color: var(--a4-navy); font-size: 11pt; }}
.a4-badge {{
  border: 1px solid var(--a4-line);
  border-radius: 999px;
  padding: 2px 9px;
  font-size: 9pt;
  white-space: nowrap;
}}
h1 {{
  margin: 0 0 6px;
  color: var(--a4-navy);
  font-size: 22pt;
  line-height: 1.1;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.01em;
}}
.a4-sub {{ margin: 0 0 10px; font-size: 11pt; max-width: 96%; }}
.a4-block {{ margin-bottom: 8px; }}
.a4-block h2, .a4-warn h2 {{
  margin: 0 0 4px;
  color: var(--a4-navy);
  font-size: 14pt;
  font-weight: 700;
}}
.a4-check {{ list-style: none; margin: 0; padding: 0; }}
.a4-check li {{
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 0 0 2px;
  font-size: 11pt;
}}
.a4-box {{
  flex: 0 0 5mm;
  width: 5mm;
  height: 5mm;
  margin-top: 2px;
  border: 1.8px solid var(--a4-ink);
  border-radius: 1px;
  background: #fff;
}}
.a4-card {{
  margin: 7px 0;
  padding: 8px 10px;
  border: 1px solid var(--a4-line);
  border-left: 4px solid var(--a4-navy);
  border-radius: 8px;
  background: var(--a4-soft);
  font-size: 10.5pt;
}}
.a4-card__title {{
  margin: 0 0 5px;
  font-size: 11pt;
  color: var(--a4-navy);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}}
.a4-card p {{ margin: 0 0 4px; }}
.a4-line {{
  display: inline-block;
  min-width: 3.5em;
  border-bottom: 1.4px solid var(--a4-ink);
}}
.a4-uline {{
  display: inline-block;
  min-width: 58%;
  border-bottom: 1.4px solid var(--a4-ink);
  min-height: 1.1em;
}}
.a4-uline--short {{ min-width: 72%; display: block; margin-top: 1px; }}
.a4-opt {{ display: inline-flex; align-items: center; gap: 3px; margin-right: 10px; }}
.a4-opt .a4-box {{ margin-top: 0; }}
.a4-warn {{
  margin: 7px 0;
  padding: 7px 9px;
  border-left: 4px solid #b77b16;
  border-radius: 6px;
  background: var(--a4-warn-bg);
  color: var(--a4-warn);
  font-size: 10.5pt;
}}
.a4-warn p {{ margin: 0; }}
.a4-cta {{
  margin: 7px 0 0;
  padding-top: 7px;
  border-top: 1px solid var(--a4-line);
  font-size: 10.8pt;
}}
.a4-cta p {{ margin: 0 0 4px; }}
.a4-cta__action {{ color: var(--a4-navy); font-size: 11.5pt; }}
.a4-foot {{
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-end;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid var(--a4-line);
}}
.a4-foot__site {{
  margin: 0 0 3px;
  font-weight: 700;
  color: var(--a4-navy);
  font-size: 10.5pt;
}}
.a4-foot__legal {{
  margin: 0;
  font-size: 9pt;
  line-height: 1.32;
  color: #52616d;
  max-width: 125mm;
}}
.a4-foot__qr {{
  flex: 0 0 auto;
  text-align: center;
  min-width: 34mm;
}}
.a4-foot__qr svg {{ display: block; width: 28mm; height: 28mm; margin: 0 auto; }}
.a4-foot__qr-label {{ margin: 2px 0 0; font-size: 8pt; color: #52616d; }}

@page {{ size: A4 portrait; margin: 0; }}
@media print {{
  html, body {{ background: #fff !important; }}
  .a4-page {{ padding: 14mm 16mm 12mm; }}
}}
</style>
</head>
<body>
<article class="a4-page" aria-label="Чек-лист A4">
  <header class="a4-top">
    {logo_block}
    <span class="a4-badge">Бесплатный чек-лист</span>
  </header>

  <h1>Как собрать документы<br>для проверки пенсионного стажа</h1>
  <p class="a4-sub">
    Краткий чек-лист для себя или родителей: выписка ИЛС, трудовая история
    и документы по спорным периодам. Без спешки и без передачи сканов в открытые чаты.
  </p>

  <section class="a4-block">
    <h2>1. Соберите документы в одну папку</h2>
    <ul class="a4-check">
      <li><span class="a4-box"></span> Выписка ИЛС из СФР</li>
      <li><span class="a4-box"></span> Трудовая книжка или сведения о трудовой деятельности</li>
      <li><span class="a4-box"></span> Справки, договоры, приказы, архивные ответы — если есть</li>
      <li><span class="a4-box"></span> Документы о смене ФИО — если фамилия менялась</li>
    </ul>
  </section>

  <section class="a4-block">
    <h2>2. Сверьте выписку ИЛС с трудовой</h2>
    <ul class="a4-check">
      <li><span class="a4-box"></span> Все места работы отражены?</li>
      <li><span class="a4-box"></span> Совпадают даты начала и окончания работы?</li>
      <li><span class="a4-box"></span> Нет ли пропусков или непонятных периодов?</li>
    </ul>
  </section>

  <section class="a4-card">
    <h2 class="a4-card__title">Если есть расхождение — отметьте один период</h2>
    <p>Период: с <span class="a4-line">__.__.____</span> по <span class="a4-line">__.__.____</span></p>
    <p>Организация / работодатель: <span class="a4-uline"></span></p>
    <p>Город / район: <span class="a4-uline"></span></p>
    <p>Должность: <span class="a4-uline"></span></p>
    <p>Есть в трудовой:
      <span class="a4-opt"><span class="a4-box"></span> да</span>
      <span class="a4-opt"><span class="a4-box"></span> нет</span>
      <span class="a4-opt"><span class="a4-box"></span> не знаю</span>
    </p>
    <p>Есть в ИЛС:
      <span class="a4-opt"><span class="a4-box"></span> да</span>
      <span class="a4-opt"><span class="a4-box"></span> нет</span>
      <span class="a4-opt"><span class="a4-box"></span> не знаю</span>
    </p>
    <p>Какие документы есть: <span class="a4-uline a4-uline--short"></span></p>
  </section>

  <section class="a4-warn">
    <h2>Важно</h2>
    <p>
      Не отправляйте в открытые чаты паспорт, СНИЛС, трудовую книжку,
      выписку ИЛС или архивные справки. Оригиналы храните у себя.
    </p>
  </section>

  <section class="a4-cta">
    <p><strong>Есть пропуск, расхождение или непонятный период?</strong></p>
    <p>
      Диагностика документов помогает сверить ИЛС, трудовую историю и справки,
      отметить возможные расхождения и подготовить план действий.
    </p>
    <p class="a4-cta__action">Напишите в MAX: <strong>«Нужна проверка документов»</strong></p>
  </section>

  <footer class="a4-foot">
    <div class="a4-foot__left">
      <p class="a4-foot__site">proverkastaza.ru</p>
      <p class="a4-foot__legal">
        Решение о назначении или перерасчёте пенсии принимает СФР.
        Сервис не гарантирует размер выплат или результат обращения.
        Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами.
      </p>
    </div>
    <div class="a4-foot__qr">
      {qr}
      <p class="a4-foot__qr-label">Страница чек-листа на сайте</p>
    </div>
  </footer>
</article>
</body>
</html>
"""


def _print_pdf(html_path: Path, pdf_path: Path) -> bool:
    if shutil.which("wkhtmltopdf"):
        subprocess.run(
            [
                "wkhtmltopdf",
                "-q",
                "--page-size",
                "A4",
                "--margin-top",
                "0",
                "--margin-bottom",
                "0",
                "--margin-left",
                "0",
                "--margin-right",
                "0",
                str(html_path),
                str(pdf_path),
            ],
            check=True,
        )
        return pdf_path.is_file()

    edge = _edge_path()
    if edge:
        subprocess.run(
            [
                str(edge),
                "--headless",
                "--disable-gpu",
                "--run-all-compositor-stages-before-draw",
                "--virtual-time-budget=3000",
                "--no-pdf-header-footer",
                f"--print-to-pdf={pdf_path}",
                html_path.resolve().as_uri(),
            ],
            check=True,
            capture_output=True,
        )
        return pdf_path.is_file()
    return False


def _screenshot_png(html_path: Path, png_path: Path) -> bool:
    edge = _edge_path()
    if not edge:
        return False
    subprocess.run(
        [
            str(edge),
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            "--window-size=794,1123",
            f"--screenshot={png_path}",
            html_path.resolve().as_uri(),
        ],
        check=True,
        capture_output=True,
    )
    return png_path.is_file()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    HTML.write_text(_html(grayscale=False), encoding="utf-8")
    html_bw = OUT_DIR / "pension-checklist-a4-print-bw.html"
    html_bw.write_text(_html(grayscale=True), encoding="utf-8")

    if not _print_pdf(HTML, PDF_STANDARD):
        raise SystemExit(
            f"Не удалось собрать PDF (нужен Edge или wkhtmltopdf). HTML: {HTML}"
        )
    print(f"Wrote {PDF_STANDARD} ({PDF_STANDARD.stat().st_size // 1024} KiB)")

    if _print_pdf(html_bw, PDF_BW):
        print(f"Wrote {PDF_BW} ({PDF_BW.stat().st_size // 1024} KiB)")

    if _screenshot_png(HTML, PNG_PREVIEW):
        print(f"Wrote {PNG_PREVIEW}")

    print("Готово. Канон рассылки:", PDF_STANDARD.name)


if __name__ == "__main__":
    main()
