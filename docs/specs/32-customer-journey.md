# Путь клиента: динамический сбор документов

**Статус:** внедрение  
**Связанные ТЗ:** [03-client-cabinet.md](03-client-cabinet.md), [13-document-ingest-v2.md](13-document-ingest-v2.md), [14-yandex-workspace.md](14-yandex-workspace.md), [20-max-private-chat-funnel.md](20-max-private-chat-funnel.md)

## Цель

Сократить путь клиента от согласия до готового комплекта документов: показывать только релевантные пункты чек-листа, принимать файлы через защищённый кабинет и личный MAX (после consent-gate), описать зеркало Яндекс.Диска в ПДн и вынести перенос трудовой в отдельную услугу.

## Зафиксированные решения

- Обязательный минимум для анализа: **выписка ИЛС** и **трудовая / сведения о стаже**.
- Паспорт, СНИЛС, банковская выписка, свидетельства детей, опека, военный билет — **только по ситуации** или по запросу специалиста.
- Банковская выписка за 12 месяцев — **staff-only**: появляется после запроса с причиной, периодом и отдельным согласием клиента.
- Личный MAX принимает файлы **только после consent-gate**; файлы попадают в единый Supabase Storage и видны в кабинете.
- Яндекс.Диск `SFRFR-cases` — закрытое зеркало (не публичный канал); банковские выписки не зеркалируются по умолчанию.
- Перенос рукописной трудовой в Word — отдельная услуга **100 ₽/разворот** (`LABOR_WORD`), с подтверждением цены до начала.

## Сценарии (`case_scenarios`)

| Код | Когда активируется | Документы |
|-----|-------------------|-----------|
| `name_change` | Смена ФИО | Свидетельство о браке / перемене имени |
| `children_care` | Уход за ребёнком | Свидетельства о рождении |
| `adoption_or_guardianship` | Опека / попечительство | Акт/решение органа опеки |
| `military_service` | Военная служба | Военный билет, справка о службе |
| `disability_or_80plus_care` | Уход за инвалидом I гр. / 80+ | Документы по периоду ухода |
| `northern_or_preferential_service` | Северный / льготный стаж | Уточняющие справки |
| `liquidated_employer_or_archive` | Ликвидированный работодатель | Архивные справки |
| `sfr_response_or_refusal` | Был ответ/отказ СФР | Заявление, ответ, опись |
| `representative` | Законный представитель | Доверенность |
| `pension_assigned` | Пенсия уже назначена | Справки СФР о размере и выплатах |
| `bank_statement_limited` | Только staff-request | Банковская выписка (узкий сценарий) |

## Модель требований

Расширение `checklist_items`:

- `requirement_code`, `scenario_code`, `category` (`required` / `conditional` / `if_available` / `staff_requested`)
- `reason_for_request`, `is_required_now`, `consent_required`
- `requested_by`, `requested_at`, `unavailable_reason`

Статусы документа: `requested`, `uploaded`, `under_review`, `accepted`, `needs_reupload`, `not_available`, `not_required`.

## API (кабинет)

- `GET /api/portal/cases/{id}/scenarios` — активные сценарии и анкета.
- `PUT /api/portal/cases/{id}/scenarios` — сохранить ответы анкеты, создать условные пункты.
- `POST /api/portal/cases/{id}/labor-transcription/estimate` — оценка разворотов.
- `POST /api/portal/cases/{id}/labor-transcription/confirm` — заказ `LABOR_WORD`.

## API (админка)

- `POST /api/admin/cases/{id}/document-requirements` — staff-request (в т.ч. банковская выписка с причиной и периодом).

## MAX

- Перед приёмом вложения: проверка `has_consent(case_id)`.
- При отсутствии согласия — CTA в кабинет, файл не сохраняется.
- **Единый чат по делу:** текстовая переписка синхронизируется между кабинетом и MAX (`case_messages`, `channel_origin` для аудита).
- **Файлы в чат MAX при активном деле не принимаются** — только загрузка через «Мои документы» в кабинете; бот отвечает с ссылкой на раздел документов.
- Доставка кабинет → MAX через `case_chat_outbox`; дедуп входящих MAX по `external_message_id`.

## Критерии приёмки

- Новый клиент видит только ИЛС и трудовую как обязательные.
- Дети/опека/банк появляются только по сценарию или staff-request.
- MAX без consent отклоняет вложения.
- Сообщение из кабинета видно в MAX и наоборот (одна лента `case_messages`).
- Файл в MAX при активном деле не попадает в документы дела.
- Перенос трудовой не стартует без подтверждения цены.
- ПДн описывают зеркало Диска; банк не зеркалируется без флага.

## Ingest, batch и группы (MVP)

- Magic bytes + лимит 20 МБ на файл; ZIP/RAR/7z и опасные форматы блокируются.
- После upload: quality report, классификация, `placement_suggestion`; статус `under_review` до проверки специалиста.
- Batch: `POST /api/portal/cases/{id}/documents/batch` — до 20 файлов, общий `upload_batch_id`.
- Прогресс: `GET /api/portal/cases/{id}/documents/{doc_id}/progress`.
- Группы страниц: `POST/GET /api/portal/cases/{id}/document-groups`.
- Скачивание: `POST /api/portal/cases/{id}/documents/bulk-download` (один файл — signed URL, несколько — ZIP).
- Подписанные заявления/обращения: `client_signed_application`, `client_signed_appeal` — PDF/DOCX.
- Черновик хронологии трудовой: `GET /api/portal/cases/{id}/labor-timeline-draft`.
- Сценарий `payout_reconciliation` — банковская выписка только после явного выбора клиента.
