# Кабинет сотрудника = основная CRM

С 2026-08-29 **amoCRM выключена** (`AMOCRM_ENABLED=0`). Код интеграции сохранён как резерв в `src/sfrfr/integrations/amocrm/`.

## Где что вести

| Что | Где |
|-----|-----|
| Этапы / воронка | Реестр admin → **Канбан** или таблица |
| Оплаты / счета / QR | Вкладка **Финансы** |
| Следующий шаг | Карточка дела → next_action |
| Отказ (LOSS) | Карточка → блок «Закрытие сделки» |
| Переписка | MAX (+ ссылки из карточки) |
| Качество | Яндекс Трекер (STAZH) |

Телефония, чаты и аналитика «из коробки» amo **не** используем.

## Канбан колонки

`new` → `in_touch` → `docs` → `payment` → `delivery` → `closed` / `lost`  
Логика: `src/sfrfr/services/sales_board.py`, UI: `apps/admin/src/lib/sales-board.ts`.

## Закрытие

`POST /api/portal/admin/cases/{id}/close`  
- `outcome=success` — без `loss_reason`  
- `outcome=lost` — обязателен `loss_reason` из канон-списка  

Миграция: `supabase/migrations/20260829190000_cases_loss_reason.sql`.

## Включить amo снова (резерв)

1. `AMOCRM_ENABLED=1` + токены в `.env`
2. Перезапуск API
3. Документы в `docs/AMO/` (исторический пакет)

Публичный лид с сайта **не** требует сделки amo, пока флаг выключен.
