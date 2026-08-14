# Воронка продаж и поля amoCRM (выдержка)

Источник: `docs/marketing-sales/spec-marketing-sales-foundation.md` §9  
Связь: [how-we-work-amocrm.md](how-we-work-amocrm.md), [tz-12-amocrm.md](tz-12-amocrm.md)  
**Операционный канон этапов/чеклистов/авто:** [playbook-funnel-checklists-automation.md](playbook-funnel-checklists-automation.md)

Поля **не** содержат тексты документов и сканы.

## Поля атрибуции / квалификации (сделка)

```text
FIRST_SOURCE
LAST_SOURCE
UTM_MEDIUM
UTM_CAMPAIGN
UTM_CONTENT
UTM_TERM
LANDING_VARIANT
AUDIENCE_SEGMENT
REGION_BUCKET
REFERRAL_CODE
PROBLEM_TYPE
LOSS_REASON
DIAGNOSTIC_PAID_AT
SERVICE_PAID_AT
RESULT_CONFIRMED_AT
SUCCESS_FEE_DUE_AT
SUCCESS_FEE_PAID_AT
```

Поля success fee — скрыты (`is_api_only`); продажи SF не включены (решение 14.08.2026).

Базовые поля ТЗ-12: `CASE_ID`, `SFRFR_CASE_URL`, `PIPELINE_STATUS`, `CHANNEL`, `SOURCE`, `CONSENT`.

## Целевые стадии (операционная воронка amo)

```text
Новый лид
→ Связались
→ Квалифицирован
→ Диагностика предложена
→ Диагностика оплачена
→ Документы в кабинете
→ Диагностика выдана
→ Сопровождение предложено
→ Сопровождение оплачено
→ Пакет выдан
→ Клиент подал в СФР
→ Результат подтверждён
→ Отзыв запрошен
→ Отзыв получен
→ Закрыто успешно

(+ системный Отказ / LOSS с обязательным LOSS_REASON)
```

Вход с сайта: **«Новый лид»**. Маппинг `pipeline_status` / `b2c_status` → колонка amo — в playbook funnel.  
Этап «Вознаграждение за результат» в колонку не выводим до юр. решения.

## Причины потери (LOSS_REASON)

```text
нецелевой вопрос
нет связи
не готов передавать документы
цена
хочет гарантию результата
нет необходимых исходных документов
выбрал самостоятельный путь
выбрал другого исполнителя
неудобен канал
другое
```

Свободный комментарий — только в CRM, без избыточных чувствительных данных.

## Операционный playbook

- Воронка, чеклисты, авто: [playbook-funnel-checklists-automation.md](playbook-funnel-checklists-automation.md)
- Карточка amo (поля + перечень документов без содержимого): [playbook-operator-amo-card.md](playbook-operator-amo-card.md)
- Квалификация: `docs/marketing-sales/playbook-sales-qualification.md`
- Трудовая → Word: `docs/marketing-sales/playbook-trudovaya-word-table.md`
