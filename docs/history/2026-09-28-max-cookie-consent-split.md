# 2026-09-28 — «Начать» в MAX больше не фиксирует согласие на cookies

## Проблема

Кнопка «Начать» в MAX (согласие на ПДн, `pdn-consent-2026-09-28`) заодно
записывала согласие на cookies сайта:

- `mark_client_pdn_consent` — `clients.cookie_consent_version` / `cookie_consent_accepted_at`;
- `_ensure_cookie_consent_row` — строка `consents` с версией `cookies-site-2026-09-22`
  (вызывалась из `accept_pdn_once` и `ensure_case_consent_from_client`).

Cookies относятся к сайту (`файлы-браузера-2026-08-03`: статистические файлы Метрики —
только после «Разрешить» в баннере). По 152-ФЗ согласие должно быть конкретным и отдельным.

## Что сделано

- `src/sfrfr/services/client_pdn_consent.py`: в `clients` пишутся только `pdn_consent_*`;
  удалены `_ensure_cookie_consent_row` и `COOKIE_CONSENT_VERSION`.
- Тест `tests/unit/test_max_cookie_consent_split.py`: «Начать» и наследование согласия
  на новое дело пишут ПДн-согласие и не пишут cookie-согласие.

## Не менялось

- Колонки `clients.cookie_consent_*` и индекс остаются (миграция `20260922130000`);
  существующие записи не трогаем, миграций нет.
- Кабинет/API cookie-поля не читают: доступ зависит только от ПДн-согласия
  (`has_consent`, `client_has_pdn_consent`) — пустое cookie-согласие ничего не блокирует.

## Хвост

- Существующие строки `cookie_consent_*` / `consents.version = cookies-site-2026-09-22`
  получены без отдельного выбора — как доказательство согласия на cookies их не использовать;
  чистка — отдельное решение владельца.
