# Playbook: сервисные vs рекламные сообщения и marketing consent

**Дата:** 2026-08-23  
**Статус:** канон + реализация журнала/гейта  
**Связано:** [clarity-funnel §5в](playbook-sales-clarity-funnel.md) · миграция `20260823180000_marketing_consents.sql` · `src/sfrfr/services/marketing_consent.py`

---

## Принцип

Для **рекламных** сообщений в MAX и других мессенджерах нужно **отдельное предварительное, добровольное и доказуемое** согласие.  
Его нельзя прятать в согласии на ПДн и нельзя делать обязательным для чек-листа, консультации или услуги.

Реклама по сетям электросвязи — только при предварительном согласии; доказывать согласие обязан отправитель; по требованию адресата — прекратить немедленно  
([прокуратура / Закон о рекламе](https://www.klgd.ru/useful/prokuratura/detail.php?ID=6391272&print=Y)).

---

## Три вида сообщений

| Вид | Пример | Согласие на рекламу |
|---|---|---|
| **Сервисное** | «Кабинет открыт», «Завтра срок загрузки ИЛС», «Документ получен», чек-лист по запросу, касания §5в, **опрос понятности после PDF** (ТЗ-27) | Обычно **нет** (в рамках активного обращения) |
| **Ответ на обращение** | Ответ на вопрос клиента, квалификация | Обычно **нет** |
| **Рекламное / маркетинговое** | Скидка, «новая услуга», рассылка материалов, «запишитесь» | **Да**, отдельно по каналу |

Сомнение → считать рекламой → не слать без `marketing_consent=granted` для канала.

Шаблонные коды:

- сервис: `service_*`, `checklist_*`, `ils_*`, `pay_*`, `cabinet_*`, `docs_*`, `diag_*`
- маркетинг: `marketing_*`, `promo_*`, `ads_*`, `newsletter_*`
- `mixed` — заблокирован до классификации

---

## Как получить согласие

### Форма сайта

Два независимых чекбокса: ПДн (обязательный) + маркетинг MAX (необязательный, **пустой по умолчанию**).  
Отказ от маркетинга не блокирует заявку. См. `scripts/wp_ensure_lead_form.php`.

### MAX — кнопки

Текст и кнопки: `src/sfrfr/integrations/max/marketing_consent_flow.py`.  
В admin: `POST /api/portal/admin/cases/{id}/marketing-consent/request`.

Команды клиента: **СТОП** / «Отписаться» → `revoked` + suppression.

### QR / double opt-in

Отдельная страница «Получать материалы» — P1 (не смешивать с бумажными списками «для связи»).

---

## Журнал и гейт

Таблица `marketing_consents` (append-only события).  
Гейт: `gate_outbound_message` в `max-reply` — marketing без granted → **403** с понятным текстом.

Поля статуса (логически):

```text
marketing_consent: granted | denied | revoked | none
marketing_channels: max / email / sms — независимо
consent_version, granted_at / revoked_at, proof_id, source
```

После `revoked`/`denied` — suppression: marketing-сценарии блокируются на backend.

---

## Карточка admin

- `GET .../marketing-consent` — статусы по каналам  
- `POST .../marketing-consent/request` — запрос в MAX  
- Composer: `message_kind` / prefix `template_code`; marketing без согласия — ошибка

Не передавать факты согласия конкретного клиента в Яндекс Трекер.

---

## Формальный текст (черновик для юриста)

См. [`docs/contracts/marketing-consent-max-draft.md`](../contracts/marketing-consent-max-draft.md).

---

## Приёмка

- [ ] Отказ от маркетинга не блокирует услугу / чек-лист  
- [ ] Согласие MAX ≠ e-mail  
- [ ] После СТОП marketing блокируется  
- [ ] Сервисные касания §5в работают без marketing consent  
- [ ] Чекбокс на форме не предустановлен  
- [ ] Тесты `tests/unit/test_marketing_consent.py`
