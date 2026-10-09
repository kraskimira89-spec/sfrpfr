"""Собрать редактируемый Word (.docx) лид-магнита A4.

Запуск:
  .\\.venv\\Scripts\\python.exe scripts/build_leadmagnet_a4_docx.py
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_LINE_SPACING
from docx.shared import Cm, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "scripts" / "assets" / "leadmagnets" / "pension-checklist-a4.docx"

CHECK_ITEMS = [
    "Выписка ИЛС из СФР (актуальная, с датой формирования)",
    "Трудовая книжка (бумажная) или выписка из электронной трудовой",
    "Справки, договоры, приказы, архивные ответы — если есть",
    "Документы о смене ФИО — если фамилия менялась",
    "Если пенсия уже назначена: справка о размере / выплатах СФР",
    "Дети / опека / льготный или северный стаж — документы по вашей ситуации",
]

VERIFY_ITEMS = [
    "Все места работы отражены в выписке ИЛС?",
    "Совпадают даты начала и окончания работы?",
    "Нет ли пропусков или непонятных периодов?",
]


def _set_run(run, *, bold: bool = False, size: int = 11) -> None:
    run.bold = bold
    run.font.size = Pt(size)
    run.font.name = "Times New Roman"


def build() -> Path:
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Cm(1.5)
    section.bottom_margin = Cm(1.5)
    section.left_margin = Cm(2)
    section.right_margin = Cm(1.5)

    title = doc.add_paragraph()
    r = title.add_run("Как собрать документы для проверки пенсионного стажа")
    _set_run(r, bold=True, size=14)

    sub = doc.add_paragraph()
    r = sub.add_run(
        "Бесплатный чек-лист сервиса «Проверка стажа». "
        "В Word удобно отмечать пункты и дописывать периоды."
    )
    _set_run(r, size=10)

    h1 = doc.add_paragraph()
    r = h1.add_run("1. Соберите документы в одну папку")
    _set_run(r, bold=True, size=12)

    for item in CHECK_ITEMS:
        p = doc.add_paragraph()
        r = p.add_run(f"☐  {item}")
        _set_run(r, size=11)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE

    h2 = doc.add_paragraph()
    r = h2.add_run("2. Сверьте выписку ИЛС с трудовой")
    _set_run(r, bold=True, size=12)

    for item in VERIFY_ITEMS:
        p = doc.add_paragraph()
        r = p.add_run(f"☐  {item}")
        _set_run(r, size=11)
        p.paragraph_format.space_after = Pt(2)

    note = doc.add_paragraph()
    r = note.add_run(
        "Если на всё «да» — сохраните папку. "
        "Если есть «нет» или «не знаю» — заполните карточку ниже."
    )
    _set_run(r, size=10)

    h3 = doc.add_paragraph()
    r = h3.add_run("Карточка спорного периода")
    _set_run(r, bold=True, size=12)

    for line in (
        "Период: с __.__.____ по __.__.____",
        "Организация / работодатель: ________________________________",
        "Город / район: ____________________________________________",
        "Должность: ________________________________________________",
        "Есть в трудовой: ☐ да  ☐ нет  ☐ не знаю",
        "Есть в ИЛС:      ☐ да  ☐ нет  ☐ не знаю",
        "Какие документы есть: ______________________________________",
    ):
        p = doc.add_paragraph()
        r = p.add_run(line)
        _set_run(r, size=11)
        p.paragraph_format.space_after = Pt(2)

    warn = doc.add_paragraph()
    r = warn.add_run(
        "Важно: не отправляйте в открытые чаты паспорт, СНИЛС, трудовую и выписку ИЛС. "
        "Документы — в личный чат MAX или кабинет на сайте."
    )
    _set_run(r, size=10)

    cta = doc.add_paragraph()
    r = cta.add_run(
        "Есть пропуск или расхождение? Напишите в чат MAX: "
        "https://max.ru/id8905998693_1_bot\n"
        "Сайт: https://proverkastaza.ru/\n"
        "Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. "
        "Решение принимает только СФР."
    )
    _set_run(r, size=10)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    return OUT


if __name__ == "__main__":
    path = build()
    print(f"OK: {path} ({path.stat().st_size} bytes)")
