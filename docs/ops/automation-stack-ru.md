# Стек автоматизации SFRFR (РФ, без Make/Albato)

**Дата:** 2026-08-22  
**Статус:** канон  
**Связано:** [playbook-funnel-checklists-automation.md](../AMO/playbook-funnel-checklists-automation.md) · [ops-amocrm-task-templates.md](../AMO/ops-amocrm-task-templates.md) · [how-we-work-amocrm.md](../AMO/how-we-work-amocrm.md)

---

## Решение

**Make.com, Albato, Zapier и аналоги не используем как ядро автоматизации.**

| Причина | Пояснение |
|---------|-----------|
| Доступность в РФ | Make.com недоступен; Albato нестабилен |
| ПДн и документы | Лиды, телефоны, дела — только в SFRFR + amo без сканов |
| Предсказуемость | Критичные цепочки — код с тестами, не no-code |
| Уже есть контур | FastAPI webhooks, amo API, GitHub Actions |

**Источник истины по делу:** Supabase + кабинет SFRFR.  
**amoCRM:** продажи, задачи оператору, атрибуция — без СНИЛС/ИЛС/сканов.

---

## Архитектура (runtime)

```text
Сайт / MAX / оплата
  → FastAPI (public_leads, payments, notifications)
  → Supabase (case, orders)
  → amoCRM sync (AmoCrmClient.sync_case)
  → MAX уведомления клиенту

Обработка документов (отдельный контур):
  → orchestrator.py → узкие AI-агенты → human_review
  → сверка ИЛС↔трудовая — детерминированный код (не LLM)
```

Код amo: `src/sfrfr/integrations/amocrm/`  
AI: `src/sfrfr/ai/orchestrator.py`

---

## Матрица сценариев

| Сценарий | Где реализовать | P | Статус |
|----------|-----------------|---|--------|
| Лид WP / форма → дело + сделка amo | код `public_leads` | P0 | **код DONE** |
| Лид MAX → дело + amo | код `max/handler` | P0 | **код DONE** |
| Задача «Первый контакт» на новую сделку | `AmoCrmClient.create_lead_task` | P0 | **код DONE** |
| `LOSS_REASON` обязателен на этапе «Отказ» | amo UI `required_statuses` | P0 | **UI владелец** — [ops-amocrm-setup](../AMO/ops-amocrm-setup.md) §4а |
| Смена колонки amo по b2c / pipeline / task | `pipeline_stages` + PATCH `status_id` | P1 | **код DONE** |
| Оплата DIAG → колонка + задача «Документы» | `payments/notify` (`task=paid:…`) | P1 | **код DONE** |
| `completed` → просьба отзыва MAX + «Отзыв запрошен» | `notifications` + `task=review_ask` | P1 | **код DONE** |
| Задача «Квалификация» при переходе в «Связались» | amo Digital Pipeline UI | P1 | **UI владелец** — [ops-amocrm-task-templates](../AMO/ops-amocrm-task-templates.md) |
| Задача «Оффер диагностики» при «Квалифицирован» | amo Digital Pipeline UI | P1 | **UI владелец** |
| Напоминание об отзыве (≥3 дня) | задача amo при `review_asked` + ручной чеклист | P2 | **код DONE** (задача); напоминание — оператор |
| Дашборд конверсий | DataLens / amo / admin | P2 | TBD |
| Webhook amo → SFRFR | — | — | **вне MVP** |
| Деплой, SEO, Webmaster | GitHub Actions + cron VPS | ops | **DONE** |
| VK Ads lead → amo | код FastAPI (предпочт.) или n8n P2 | P2 | TBD |
| Черновики постов / Wordstat | Cursor offline (Marketing/VK чаты) | — | **не runtime** |

> На этапе «Новый лид» задачу создаёт **SFRFR** — дублирующий триггер в Digital Pipeline **не** нужен.

---

## AI-агенты: где да, где нет

### Да (runtime, продукт)

Цепочка в `orchestrator.py`: OCR → classify → extract → **audit (код)** → reason → draft → **human_review**.

- Расширять **точечно** (новый узкий агент на шаг).
- Не «swarm» и не автономные агенты на проде.

### Нет (runtime)

- Смена этапа amo / квалификация лида LLM-ом.
- Авто-ответы клиенту без human_review по документам.
- Маркетинговая автопубликация пакетом (правило `blog-manual-only`).

### Да (offline, Cursor)

Чаты AMO / VK / Marketing — черновики, чеклисты, семантика. Без автопубликации и без ПДн в промптах.

---

## amoCRM: код vs UI

| Что | Кто |
|-----|-----|
| Создание/обновление сделки, поля, sync колонок, задачи на ключевых событиях | **SFRFR API** |
| Задачи на «Связались» / «Квалифицирован» | **Digital Pipeline** (один раз в UI) |
| Обязательность `LOSS_REASON` на отказе | **UI воронки** |
| Сканы, СНИЛС, ИЛС | **запрещено** |

Настройка: [ops-amocrm-setup.md](../AMO/ops-amocrm-setup.md) · шаблоны задач: [ops-amocrm-task-templates.md](../AMO/ops-amocrm-task-templates.md)

---

## Ops и cron (не no-code SaaS)

| Задача | Инструмент |
|--------|------------|
| Деплой VPS | `.github/workflows/deploy-vps.yml` |
| Webmaster diagnostics | `scripts/yandex_webmaster_diagnostics.py` + workflow |
| dbt / аналитика | VPS cron + GitHub Actions |
| Ручной seed WP | SSH `wp_seed_*.sh` при пустой очереди deploy |

---

## n8n self-hosted (P2, опционально)

**Не установлен.** Рассмотреть только если появятся **3+ некритичных** glue-сценария вне amo и FastAPI.

| Можно | Нельзя |
|-------|--------|
| Служебные уведомления без ПДн | Дела, документы, телефоны клиентов |
| Простой webhook VK → служебный канал | Хранение токенов в git |
| Дублирование уже существующего кода | Замена `public_leads` / payments |

Шаблон env: [n8n.env.example](n8n.env.example) (без деплоя в этом репо).

Когда подключать: после стабильного baseline amo + Директ, при явной нехватке «мелкого клея».

---

## Антипаттерны

- Make.com / Albato / Zapier как ядро CRM или оплат.
- LLM-цепочки для смены этапа amo или авто-продаж.
- Swarm агентов на проде.
- Google Sheets с ПДн (только обезличенные whitelist-строки).
- Webhook amo → SFRFR до отдельного ТЗ и модели конфликтов статусов.

---

## Когда пересмотреть

| Порог | Действие |
|-------|----------|
| >30–50 лидов/мес, оператор перегружен | Усилить amo DP + код, не Make |
| >100 дел/мес, много мелких интеграций | Пилот n8n на VPS (без ПДн) |
| B2B / white-label | Оркестратор в коде, не no-code |

---

## Связанные документы

- [AMO README](../AMO/README.md)
- [spec-marketing-sales-foundation.md](../marketing-sales/spec-marketing-sales-foundation.md) §9
- [VK research-vk-api.md](../VK/research-vk-api.md) — лиды VK
- История решения: [2026-08-22-automation-stack.md](../history/2026-08-22-automation-stack.md)
