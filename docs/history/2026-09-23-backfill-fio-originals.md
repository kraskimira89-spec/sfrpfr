# 2026-09-23 — Backfill MAX/uploads → ФИО-зеркало

## Цель

Уже загруженные клиентские файлы (local uploads + pension-docs) сохранить
как новые оригиналы: `storage/uploads/{case_id}/` + `SFRFR-cases/{ФИО}/incoming/`.

## Решение

- `backfill_case_originals_to_fio` + CLI `yandex-disk-backfill-fio-originals`
- Идемпотентность: `storage/backfill_fio_seen.json` по `case_id:sha256` (без ПДн)
- Local source: `persist_local=False` (не плодить копии)
- Storage source: `persist_local=True`

## Проверено

`pytest tests/unit/test_backfill_case_originals.py` (+ related mirror/backfill)
