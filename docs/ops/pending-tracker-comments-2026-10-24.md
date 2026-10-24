# Ожидающие комментарии Трекера (API был недоступен)

Писать **только** после: перечитать issue → убедиться, что аналогичного комментария ещё нет → `issue_add_comment` → повторное чтение.

## SFRFR-84

```md
## Матрица 16 критериев (арифметика)

Файл: `docs/ops/sfrfr-84-criteria-evidence-matrix-2026-10-24.md`

- 13 unit / 1 N/A (#9) / 1 live (#15) / 1 передано в SFRFR-85 (#16) = **16**
- Staff UI (SFRFR-91) **вне** счётчика 16
- Передача в 85 ≠ выполнение; закрытие 84 блокируют #15 live и решение по #16
- PR #259 без merge-разрешения
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
## Кандидат receipt:… (диагностика)

History: `docs/history/2026-10-24-sfrfr-93-receipt-ocr-candidate.md`

- payment `89be641d…` provider=receipt_ocr, id=receipt:{order}
- Ошибка на **fetch_payment**; create **не** вызывался; attempts=0, streak=2
- Источник: `confirm_order_from_receipt`
- Фильтр выборки: PR #260 (без auto-merge); строку БД не меняли; окно не перезапускали
```

## Статус синхронизации

| Issue | Запись | Повторное чтение |
|---|---|---|
| SFRFR-84 | ⬜ | ⬜ |
| SFRFR-85 | ⬜ | ⬜ |
| SFRFR-93 | ⬜ | ⬜ |
