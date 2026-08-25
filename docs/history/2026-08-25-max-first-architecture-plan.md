# История: MAX-first архитектура (фаза 0)

**Дата:** 2026-08-25  
**Контур:** product / MAX / cabinet

## Что сделано

- Обследован код: cabinet auth (OTP, pair-code, magiclink `token_hash`), MAX upload ban, consents, ЮKassa webhook, `secure_share_links` (только PDF диагностики).
- Написан план: [`docs/architecture/max-first-secure-pages.md`](../architecture/max-first-secure-pages.md).
- Sprint 2–4 и код Sprint 1 **не реализовывались** (безопасная остановка на документе).
- Обновлены индексы: `docs/MAX/README.md`, `docs/specs/README.md`.
- Issue в очереди SFRFR: **SFRFR-23**.

## Вердикт обследования

Много кирпичей уже есть (MAX intake, запрет сканов в чате, оплаты, узкий diag-share). Нет generic secure action links с `purpose` и UI «одно действие без регистрации». Cabinet оставляем.

## Следующий шаг

Sprint 1 за флагами (`MAX_FIRST_*` / `SECURE_ACTION_*`) — только после явного go; не включать на prod без staging.
