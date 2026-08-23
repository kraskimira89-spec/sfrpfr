# 2026-08-23 — Mobile: cookie, капча, согласие на форме лида

## Проблема

На mobile у формы заявки:

1. Sticky «Оставить заявку» перекрывала баннер согласия на cookies (z-index).
2. SmartCaptcha уезжала за край формы.
3. Текст «Даю согласие» выглядел вертикальным (чекбокс попадал в узкую колонку grid рядом с submit).
4. Submit без галочки согласия не показывал предупреждение.

## Фикс

- `sfrfr-yandex-metrika.php` — cookie-баннер `z-index: 10050`, на mobile `bottom` над sticky CTA + safe-area.
- `sfrfr-landing.css` — sticky CTA `z-index: 900`; overflow/scale капчи; flex-ряд чекбокса; `grid-column: 1 / -1` для consent.
- `sfrfr-recaptcha-lead.js` — проверка ПДн-согласия + alert/inline warn; не переписывать marketing-consent; перенос marketing в channel.
- `sfrfr-recaptcha-lead.php` — фильтр лейбла только для `.sfrfr-lead-consent`.

Проверка: https://proverkastaza.ru/#zayavka (mobile / DevTools).
