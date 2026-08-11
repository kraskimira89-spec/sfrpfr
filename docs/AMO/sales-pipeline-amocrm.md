# Воронка продаж и поля amoCRM (выдержка)

Источник: `docs/marketing-sales/spec-marketing-sales-foundation.md` §9  
Связь: [how-we-work-amocrm.md](how-we-work-amocrm.md), [tz-12-amocrm.md](tz-12-amocrm.md)

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

Поля success fee — только после юр. утверждения модели; до этого не в LTV/CAC.

Базовые поля ТЗ-12: `CASE_ID`, `SFRFR_CASE_URL`, `PIPELINE_STATUS`, `CHANNEL`, `SOURCE`, `CONSENT`.

## Целевые стадии (бизнес-воронка)

```text
Новое обращение
→ Связались
→ Квалифицирован
→ Диагностика предложена
→ Диагностика оплачена
→ Документы получены
→ Диагностика выдана
→ Сопровождение оплачено
→ Пакет выдан
→ Результат подтверждён            # если применимо
→ Вознаграждение за результат оплачено  # только для утверждённой модели
→ Закрыто успешно
```

На аккаунте MVP этап входа с сайта: **«Новый лид»** (см. ops). Полное совпадение имён с `pipeline_status` SFRFR в MVP не обязательно — статус дублируется в поле `PIPELINE_STATUS`.

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

- Карточка amo (поля + перечень документов без содержимого): [playbook-operator-amo-card.md](playbook-operator-amo-card.md)
- Квалификация: `docs/marketing-sales/playbook-sales-qualification.md`
- Трудовая → Word: `docs/marketing-sales/playbook-trudovaya-word-table.md`
