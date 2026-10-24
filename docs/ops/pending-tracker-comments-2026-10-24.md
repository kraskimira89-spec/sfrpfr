# Ожидающие комментарии Трекера

Писать **только** после: перечитать issue → убедиться, что аналогичного комментария ещё нет → `issue_add_comment` → повторное чтение.

## SFRFR-84

```md
## Матрица 16 критериев (арифметика)

Файл: `docs/ops/sfrfr-84-criteria-evidence-matrix-2026-10-24.md` (PR #259)

- 13 unit + 1 N/A + 1 live MAX + 1 зависимость от SFRFR-85 = **16**
- Staff UI (SFRFR-91) **вне** счётчика 16
- Закрытие 84 блокируют live MAX и SFRFR-85
- PR #259 без auto-merge; head `7f682dfd`, CI зелёный
```

## SFRFR-85

```md
## Безопасный разбор клик→флаги

Матрица: `docs/ops/sfrfr-85-click-flags-matrix-2026-10-24.md`

- Холодный клик без soft-ask не изобретает completed (тест есть)
- Prior soft-ask → OFFER_REVIVE + gaps; дефекта кода в срезе не подтверждено
- Живые сообщения не трогали; PR кода пока не требуется
```

## SFRFR-93

```md
## Кандидат receipt:… (диагностика + follow-up)

History: `docs/history/2026-10-24-sfrfr-93-receipt-ocr-candidate.md` (обезличено)

- provider=receipt_ocr, id=`receipt:{order}` (полные UUID не в комментарии)
- Ошибка на **fetch_payment**; create **не** вызывался; attempts=0, streak=2
- Источник: `confirm_order_from_receipt`
- PR #260 follow-up: exclude OCR из reconcile+stale; контракт exclude≠whitelist; CI зелёный head `32167e3c`; без auto-merge
- После deploy: отдельно фиксировать тики без OCR-кандидата; в 24ч-отчёте разделить до/после
```

## Статус синхронизации

| Issue | Запись | Повторное чтение |
|---|---|---|
| SFRFR-84 | ⬜ | ⬜ |
| SFRFR-85 | ⬜ | ⬜ |
| SFRFR-93 | ⬜ | ⬜ |
