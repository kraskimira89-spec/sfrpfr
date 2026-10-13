# 2026-10-13 — юрдокументы: рабочие БД на РЕГ.РУ

## Зачем

После cutover SFRFR-73 (рабочий URL `supabase2.proverkastaza.ru` → ВМ РЕГ.РУ
`194.67.116.168`) публичные политика и согласие всё ещё писали, что рабочие базы —
в инфраструктуре ООО «ЯНДЕКС.ОБЛАКО». Это расходилось с фактом обработки.

## Что обновлено

Редакции `pdn-policy-2026-10-13` / `pdn-consent-2026-10-13`:

- рабочие БД, аутентификация и закрытое хранилище — ООО «РЕГ.РУ»;
- ООО «ЯНДЕКС.ОБЛАКО» — резервные копии / DR и сервисы (SmartCaptcha, Vision OCR,
  AI Studio, Postbox);
- краткосрочный аварийный буфер заявок на сервере приложения при недоступности БД;
- `CURRENT_CONSENT_VERSION` → `pdn-consent-2026-10-13` (повторный запрос согласия).

Оферта `offer-2026-09-09` и cookies `файлы-браузера-2026-08-03` **без изменений**
(цены, каналы оплаты, Метрика не менялись по сути обработки).

Синхронно: `rkn-notification-2026-09.md` (места БД, срок до 15.11.2026),
`processors-assignment-review-2026-09.md` (роль РЕГ.РУ расширена — DPA срочно).

## Live до деплоя

Сверка 13.10.2026: live = репо на старых редакциях `*-2026-09-28` / оферта /
cookies — расхождений live↔репо не было; расхождение было репо↔факт cutover.

## Не подтверждено / владельцу

- Акт удаления Supabase Cloud — без него в письме РКН нельзя писать
  «трансграничной передачи нет».
- DPA / поручение с РЕГ.РУ (или Рег.облако ФЗ-152).
- Подача информационного письма в РКН (черновик обновлён).

## Файлы

- `docs/contracts/pdn-policy.md`, `pdn-consent.md`
- `scripts/assets/sfrfr-privacy.html`, `sfrfr-consent.html`
- `docs/contracts/rkn-notification-2026-09.md`
- `docs/contracts/processors-assignment-review-2026-09.md`
- `src/sfrfr/db/case_repository.py`, `src/sfrfr/api/schemas/portal.py`
- `apps/cabinet/src/components/client-cabinet.tsx`, `web/max-miniapp/app.js`
- `tests/unit/test_legal_edition_2026_10_13.py`
