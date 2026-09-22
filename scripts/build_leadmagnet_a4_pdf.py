"""Сборка PDF лид-магнита A4 (1 стр.) из HTML через Chrome/Edge/wkhtmltopdf.

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
# Публичные URL (канон config / ТЗ-23/24) — ссылки и QR на листе.
URL_SITE = "https://proverkastaza.ru/"
URL_BOT = "https://max.ru/id8905998693_1_bot?startapp"
URL_CHANNEL = "https://max.ru/channel_proverkastaza"
URL_CHAT = "https://max.ru/id8905998693_1_bot"
QR_LINKS: tuple[tuple[str, str], ...] = (
    ("Сайт", URL_SITE),
    ("Чат-бот", URL_BOT),
    ("Канал", URL_CHANNEL),
    ("Личный чат", URL_CHAT),
)
PDF_STANDARD = OUT_DIR / "pension-checklist-a4-standard.pdf"
PDF_BW = OUT_DIR / "pension-checklist-a4-bw.pdf"
PNG_PREVIEW = OUT_DIR / "pension-checklist-a4-preview.png"


def _chromium_path() -> Path | None:
    """Edge или Chrome (headless --print-to-pdf)."""
    for candidate in (
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ):
        if candidate.is_file():
            return candidate
    return None


def _logo_data_uri() -> str:
    if not LOGO.is_file():
        return ""
    encoded = base64.b64encode(LOGO.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _qr_svg(url: str) -> str:
    qr = segno.make(url, error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=3, border=1, dark="#1b486c", light="#ffffff")
    return buf.getvalue().decode("utf-8")


def _qr_grid_html() -> str:
    cells: list[str] = []
    for label, url in QR_LINKS:
        short = url.replace("https://", "")
        cells.append(
            "<div class=\"a4-qr-cell\">"
            f"{_qr_svg(url)}"
            f"<p class=\"a4-qr-cell__label\">{label}</p>"
            f"<p class=\"a4-qr-cell__url\">{short}</p>"
            "</div>"
        )
    return '<div class="a4-qr-grid">' + "".join(cells) + "</div>"


def _html(*, grayscale: bool = False) -> str:
    logo = _logo_data_uri()
    logo_block = (
        f'<img class="a4-logo" src="{logo}" alt="Проверка стажа" width="120" height="32">'
        if logo
        else '<span class="a4-brand">Проверка стажа</span>'
    )
    bw = " bw" if grayscale else ""
    qr_grid = _qr_grid_html()
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
  background: #fff;
  color: var(--a4-ink);
  font-family: "PT Sans", "Noto Sans", Arial, sans-serif;
  font-size: 11pt;
  line-height: 1.35;
}}
html.bw, html.bw body {{ filter: grayscale(1); }}
.a4-page {{
  width: 210mm;
  min-height: 297mm;
  margin: 0 auto;
  padding: 11mm 13mm 9mm;
}}
.a4-top {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 5px;
}}
.a4-logo {{ display: block; height: 26px; width: auto; }}
.a4-brand {{ font-weight: 700; color: var(--a4-navy); font-size: 12pt; }}
.a4-badge {{
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--a4-soft);
  color: var(--a4-navy);
  font-size: 9pt;
  font-weight: 700;
}}
h1 {{
  margin: 3px 0 5px;
  font-size: 16.5pt;
  line-height: 1.12;
  color: var(--a4-navy);
  text-transform: uppercase;
  letter-spacing: 0.01em;
}}
.a4-sub {{ margin: 0 0 6px; font-size: 10pt; color: #44515c; }}
.a4-block {{ margin: 0 0 5px; }}
.a4-block h2 {{
  margin: 0 0 3px;
  font-size: 11.5pt;
  color: var(--a4-navy);
}}
.a4-check {{ list-style: none; margin: 0; padding: 0; }}
.a4-check li {{
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin: 0 0 2px;
  font-size: 10pt;
}}
.a4-box {{
  flex: 0 0 4.2mm;
  width: 4.2mm;
  height: 4.2mm;
  margin-top: 2px;
  border: 1.4px solid var(--a4-navy);
  border-radius: 1px;
}}
.a4-card {{
  margin: 5px 0;
  padding: 6px 8px;
  border-radius: 6px;
  background: var(--a4-soft);
}}
.a4-card__title {{
  margin: 0 0 3px;
  font-size: 10pt;
  color: var(--a4-navy);
  text-transform: uppercase;
}}
.a4-card p {{ margin: 0 0 2px; font-size: 9.5pt; }}
.a4-line {{ letter-spacing: 0.08em; }}
.a4-uline {{
  display: inline-block;
  min-width: 90mm;
  border-bottom: 1px solid var(--a4-line);
  height: 1.05em;
  vertical-align: bottom;
}}
.a4-uline--short {{ min-width: 65mm; }}
.a4-opt {{ display: inline-flex; align-items: center; gap: 4px; margin-right: 8px; }}
.a4-warn {{
  margin: 5px 0;
  padding: 5px 7px;
  border-left: 4px solid #b77b16;
  border-radius: 6px;
  background: var(--a4-warn-bg);
  color: var(--a4-warn);
  font-size: 9.5pt;
}}
.a4-warn p {{ margin: 0; }}
.a4-cta {{
  margin: 5px 0 0;
  padding-top: 5px;
  border-top: 1px solid var(--a4-line);
  font-size: 9.5pt;
}}
.a4-cta p {{ margin: 0 0 2px; }}
.a4-cta__action {{ color: var(--a4-navy); font-size: 10.5pt; }}
.a4-links {{
  margin: 5px 0 4px;
  padding: 5px 7px;
  border-radius: 6px;
  background: #f7fafc;
  border: 1px solid var(--a4-line);
  font-size: 9pt;
}}
.a4-links h2 {{
  margin: 0 0 3px;
  font-size: 10.5pt;
  color: var(--a4-navy);
}}
.a4-links ul {{ margin: 0; padding-left: 15px; }}
.a4-links li {{ margin: 0 0 1px; }}
.a4-links a {{ color: var(--a4-navy); text-decoration: none; word-break: break-all; }}
.a4-foot {{
  margin-top: 4px;
  padding-top: 4px;
  border-top: 1px solid var(--a4-line);
}}
.a4-foot__legal {{
  margin: 0 0 5px;
  font-size: 8pt;
  line-height: 1.28;
  color: #52616d;
}}
.a4-qr-grid {{
  display: flex;
  justify-content: space-between;
  gap: 5px;
}}
.a4-qr-cell {{
  flex: 1 1 0;
  text-align: center;
  min-width: 0;
}}
.a4-qr-cell svg {{
  display: block;
  width: 20mm;
  height: 20mm;
  margin: 0 auto;
}}
.a4-qr-cell__label {{
  margin: 2px 0 0;
  font-size: 8pt;
  font-weight: 700;
  color: var(--a4-navy);
}}
.a4-qr-cell__url {{
  margin: 0;
  font-size: 6pt;
  line-height: 1.15;
  color: #52616d;
  word-break: break-all;
}}

@page {{ size: A4 portrait; margin: 0; }}
@media print {{
  html, body {{ background: #fff !important; }}
  .a4-page {{ padding: 11mm 13mm 9mm; }}
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
      Не отправляйте в открытые чаты и в канал паспорт, СНИЛС, трудовую книжку,
      выписку ИЛС или архивные справки. Оригиналы храните у себя.
      Файлы — только в личный чат MAX после согласия или в кабинет на сайте.
    </p>
  </section>

  <section class="a4-cta">
    <p><strong>Есть пропуск, расхождение или непонятный период?</strong></p>
    <p>
      Диагностика документов помогает сверить ИЛС, трудовую историю и справки,
      отметить возможные расхождения и подготовить план действий.
    </p>
    <p class="a4-cta__action">Напишите в личный чат MAX: <strong>«Нужна проверка документов»</strong></p>
  </section>

  <section class="a4-links" aria-label="Ссылки и QR">
    <h2>Куда обратиться</h2>
    <ul>
      <li><strong>Сайт:</strong> <a href="{URL_SITE}">{URL_SITE}</a></li>
      <li><strong>Чат-бот MAX:</strong> <a href="{URL_BOT}">{URL_BOT}</a></li>
      <li><strong>Канал MAX:</strong> <a href="{URL_CHANNEL}">{URL_CHANNEL}</a></li>
      <li><strong>Личный чат с ботом:</strong> <a href="{URL_CHAT}">{URL_CHAT}</a></li>
    </ul>
  </section>

  <footer class="a4-foot">
    <p class="a4-foot__legal">
      Решение о назначении или перерасчёте пенсии принимает СФР.
      Сервис не гарантирует размер выплат или результат обращения.
      Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами.
    </p>
    {qr_grid}
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

    browser = _chromium_path()
    if browser:
        subprocess.run(
            [
                str(browser),
                "--headless=new",
                "--disable-gpu",
                "--run-all-compositor-stages-before-draw",
                "--virtual-time-budget=5000",
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
    browser = _chromium_path()
    if not browser:
        return False
    subprocess.run(
        [
            str(browser),
            "--headless=new",
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
            f"Не удалось собрать PDF (нужен Chrome, Edge или wkhtmltopdf). HTML: {HTML}"
        )
    print(f"Wrote {PDF_STANDARD} ({PDF_STANDARD.stat().st_size // 1024} KiB)")

    if _print_pdf(html_bw, PDF_BW):
        print(f"Wrote {PDF_BW} ({PDF_BW.stat().st_size // 1024} KiB)")

    if _screenshot_png(HTML, PNG_PREVIEW):
        print(f"Wrote {PNG_PREVIEW}")

    print("Готово. Канон рассылки:", PDF_STANDARD.name)


if __name__ == "__main__":
    main()
