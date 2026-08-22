# 2026-08-22 — Стек автоматизации без Make/Albato

## Решение

- Критичные цепочки (лиды, оплаты, amo, MAX) — **код + webhooks** в FastAPI.
- Make.com / Albato / Zapier **не** подключаем как ядро.
- AI-агенты runtime — только `orchestrator.py` для документов; CRM/маркетинг — детерминированные правила.
- amo Digital Pipeline + `LOSS_REASON` required — **ручная настройка UI** (владелец).
- n8n self-hosted — опционально P2, без деплоя; шаблон `docs/ops/n8n.env.example`.

## Артефакты

- `docs/ops/automation-stack-ru.md` — матрица сценариев P0/P1/P2.
- Обновлены ops amo, playbook automation, ссылки AMO/VK/marketing.

## Код amo P0/P1

Уже в репо до этого решения: sync колонок, задачи на лид/diag_paid/review_ask, отзыв в MAX.
