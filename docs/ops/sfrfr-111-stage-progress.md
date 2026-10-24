# SFRFR-111: прогресс этапов (без merge)

| Этап | Issue | Статус |
|---|---|---|
| Родитель | SFRFR-111 | open; depends on SFRFR-110 |
| 1 Аудит/контракт | SFRFR-112 | выполнен: `sfrfr-111-primary-doc-precheck-contract.md` |
| 2 Кнопка/запуск | SFRFR-113 | reuse + `require_case_exact` на request-review |
| 3 Сопоставление | SFRFR-114 | `primary_doc_precheck` + усиленный `audit_ils` в job.result |
| 4 Резюме/рекомендация | SFRFR-115 | client_summary; paid только при discrepancies + каталог |
| 5 MAX | SFRFR-116 | enqueue notify + контекстные кнопки (не live) |
| 6 Приёмка | SFRFR-117 | unit 18 passed; PG/browser/live — остаток |

## Тесты

```text
.\.venv\Scripts\python.exe -m pytest tests/unit/test_primary_doc_precheck.py tests/unit/test_staff_document_check.py -q --basetemp=.tmp_pytest_precheck
→ 18 passed
```

## Не сделано / блокеры без отдельного OK

- Merge / deploy / live MAX
- Полный callback-handler precheck:* в MAX handler
- Browser E2E / worker на реальной БД
- Извлечение периодов из OCR внутри job (сейчас сверка по `case_pipeline_data` periods)

## Запреты соблюдены

Нет автопродажи при no_discrepancy / insufficient; нет гарантий пенсии; нет автозаказа оплаты.
