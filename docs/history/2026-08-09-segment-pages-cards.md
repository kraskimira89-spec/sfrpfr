# 2026-08-09 — секции услуговых страниц как на главной

## Figma
- Файл: https://www.figma.com/design/PgQcoSe72l568LiGF6BRE2
- Эталон: Segment / Pre-retirement (desktop) — чередование band/white, 3 карточки, 4 шага, FAQ.
- Компакт: Segment / Compact (no process).

## Сайт
- `proverka-stazha-pered-pensiey.html` — cards + steps--4 + faq.
- `proverka-severnogo-stazha.html`, `pomoch-rodstvenniku-proverit-stazh.html` — cards + faq + note.
- CSS: `.sfrfr-steps--row.sfrfr-steps--4` на широком экране.
- Копирайт пунктов сохранён; одиночных карточек в разделе нет.
- Контуры: нечётный section — акцент слева, чётный — справа (карточки, шаги, note, FAQ); в Figma то же.
- `/proverka-stazha/`: крупные карточки `sfrfr-cards--2 sfrfr-cards--lg`, в разделе ровно 2 рядом.
- Списки в карточках — маркированные `ul/li` (+ тарифы на главной и `/tarify/`).
- `/proverka-stazha-pered-pensiey/`: 2×2 крупные карточки — Кому (ol) | Что проверяем (ul); Что получаете (ul) | Как проходит (ul).
