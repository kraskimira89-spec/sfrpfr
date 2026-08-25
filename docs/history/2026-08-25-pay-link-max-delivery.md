# 2026-08-25 — Доставка ссылки/QR ЮKassa клиенту в MAX

## Решение

Единый оркестратор `issue_and_deliver_pay_link`: счёт ЮKassa → `pay_url` → опционально MAX (текст + кнопка «Оплатить» + QR PNG).

## Изменения

- `src/sfrfr/services/pay_link.py` — `PayLinkError`, `issue_and_deliver_pay_link`, `maybe_auto_send_pay_link_after_draft`
- Admin pay-link / remind переведены на оркестратор; remind шлёт кнопку+QR
- Флаг `MAX_PAY_LINK_AUTO_SEND` (default 0) — автоотправка после черновика счёта
- Playbook: `docs/ops/playbook-pay-link-to-client.md`

## Не делали

- SMS/email доставка
- Secure `purpose=pay`
- Cutover FSM MAX (Sprint 4)
