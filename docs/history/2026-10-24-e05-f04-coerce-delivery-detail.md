# 2026-10-24: E05/F04 — coerce PolicyReply + detail доставки

## Проверка баг-репорта

1. **«Нет retry при enqueued»** — по канону `sfrfr-110-null-fallback-delivery-check.md` второй `_reply` при `enqueued=True` запрещён (дубль с outbox). Retry в handler не добавляли.
2. **MaxHandleResult не различал исход** — да: теперь `detail` = `caller_outcome` / `reason`.
3. **policy без валидации** — да: `coerce_policy_reply` отбрасывает пустой text, нормализует attachments/action; llm_chat пропускает пустой перехват в LLM.
