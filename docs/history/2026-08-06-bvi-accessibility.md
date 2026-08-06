# 2026-08-06 — версия для слабовидящих (BVI)

## Что сделано

- Установлен плагин WordPress **Button visually impaired** (`button-visually-impaired`).
- Опция `bviActive=true`, цвета кнопки под бренд (`#1e4e79`).
- Кнопка «Версия для слабовидящих»:
  - полоса под шапкой (`astra_header_after`);
  - блок в футере (контакты).
- Скрипты: `scripts/wp_ensure_bvi.sh`, `scripts/wp_ensure_bvi.php` (вызываются из apply/deploy).

## Замечание

Плагин давно не обновлялся на wordpress.org — после обновлений WP/Astra проверять кнопку и панель. Это панель удобства, не полная WCAG-сертификация.
