# 2026-09-22 — Layout зеркала дела на Яндекс.Диск

## Решение

Папка дела = **UUID** (номер дела), без ФИО/телефона/СНИЛС в пути.

```text
disk:/SFRFR-cases/{case_id}/
  incoming/     ← сканы клиента
  outgoing/     ← подписанные / подготовленные заявления
  chat/history.md
  meta.txt      ← только case_id + layout
```

Primary по-прежнему Supabase `pension-docs`. Диск — best-effort.

## Код

- `disk.py`: `CASE_SUBFOLDERS`, `ensure_case_layout`, `upload_case_file(subfolder=…)`, `upload_case_chat_history`
- `case_mirror.py`: routing incoming/outgoing, экспорт чата + throttle 15 мин
- CLI: `yandex-disk-case-layout`, `yandex-disk-export-chat`
- Хук: после записи в `case_messages` и после успешного зеркала документа

## Проверено

`pytest tests/unit/test_case_mirror.py tests/unit/test_yandex_workspace.py`
