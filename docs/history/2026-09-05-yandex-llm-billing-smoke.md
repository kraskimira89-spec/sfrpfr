# 2026-09-05 — Yandex LLM: billing / smoke / docs

## Факты

- Локальный smoke `scripts/_tmp_check_yandex_llm.py` с env из `secrets/yandexAI_studio.env`: `available=True`, `chat_ok`, model `deepseek-v4-flash`, folder LLM `b1gp3rqkf5t6kqmqaf7c` (ключ не печатали).
- Prod: ранее подтверждено `ops_llm_enabled=yes` (health).
- Folder mismatch: billing/инфра `default` `b1g0mhpm9tr4lrurk1bu` ≠ LLM-ключ `b1gp3rqkf5t6kqmqaf7c` — зафиксировано в `docs/ops/yandex-cloud-billing-unblock.md`.

## Доки

- Обновлён чеклист billing-unblock (API-доказательства; баннер UI — владельцу).
- Промпт AI Studio + `Yandex AI Studio/02-…`: канон DeepSeek, не dual-model YandexGPT Pro.

## Владельцу

- Подтвердить в консоли исчезновение баннера блокировки.
- При необходимости: `/opt/sfrfr/.env` содержит `YANDEX_*` с folder ключа.
