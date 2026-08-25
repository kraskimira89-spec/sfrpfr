# История: MAX-first Sprint 1 — secure action links

**Дата:** 2026-08-25  
**Контур:** product / MAX / security  
**Tracker:** [SFRFR-23](https://tracker.yandex.ru/SFRFR-23)

## Что сделано

- Feature flags (default **off**): `MAX_FIRST_FUNNEL_ENABLED`, `SECURE_ACTION_LINKS_ENABLED`, `SECURE_UPLOAD_ENABLED`, `SECURE_RESULT_VIEW_ENABLED`, `MAX_SECURE_LINK_BUTTONS_ENABLED`, `SECURE_LINK_PEPPER`.
- Миграция `supabase/migrations/20260825140000_secure_action_links.sql` — таблицы `secure_action_links`, `secure_action_events` (RLS, service-role; **не** трогает `secure_share_links`).
- Пакет `src/sfrfr/secure_links/`: CSPRNG ≥32 bytes, HMAC-SHA256 hash + prefix, create/verify/revoke/supersede; при флаге OFF — явный `SecureLinksDisabled`.
- Unit-тесты: create→verify, expired/revoked/max_uses/wrong purpose, raw не в storage, flag off.
- Обновлён `docs/architecture/max-first-secure-pages.md` (Sprint 1 ✅).

## Что не трогали (намеренно)

- MAX handler / FSM / кнопки в боте
- UI `/secure/[token]` в Next
- Admin UI, payment webhook wiring
- Cabinet OTP / pair-code / magiclink Auth
- `/diag-share` и `secure_share_links`
- Публичные CTA «личный кабинет»

## Как включить на staging

```text
SECURE_ACTION_LINKS_ENABLED=1
# опционально отдельный pepper:
SECURE_LINK_PEPPER=<random>
```

Остальные флаги (`MAX_FIRST_FUNNEL_*`, upload/result/buttons) оставить `0` до Sprint 2–4.

## Следующий шаг

Sprint 2: consent + view PDF по ссылке (роуты/страницы), без cutover MAX FSM.
