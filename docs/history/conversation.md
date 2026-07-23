# История беседы (кратко)

## 2026-07-23

- DOCX ТЗ-10: strip `**`/` из списков/таблиц/заголовков; `*.docx` в `.gitignore`, файл не коммитить (сборка `scripts/render_landing_tz_docx.py`).
- Реализован ТЗ-09: единый portal для mini-app (MAX auth), link_token, deep-link case, CTA уведомлений.
- Реализован ТЗ-08: feedback→RAG registry, rejected вне поиска, тесты приёмки knowledge.
- Реализован ТЗ-07 MVP: публичный lead API, WP CTA выбора канала, MAX /docs+/draft, оплата с fallback.
- Реализован ТЗ-06: Taganay webhook, Sheets без ПДн, ЮKassa pay+webhook, тесты RLS/Storage/Sheets.
- Реализован ТЗ-05: health/ops, безопасные логи, CI gate, ранбук.
- Логотип для светлого фона на витрине (Astra + favicon + hero) и в иконках cabinet/admin.
- Письмо reg.ru: DNS `cabinet`/`admin` добавлены; порты 80/443 открыты. Подняты HTTPS + Next.js кабинеты на VPS (пароль root от них **не нужен** — есть deploy key).
- Накатил миграции Supabase + CLI `staff-grant`/`staff-list` для первого admin.
- Реализован ТЗ-04 кабинет сотрудников с учётом ТЗ-09 (каналы MAX/веб в дашборде и карточке; admin не в mini-app).
- Реализован ТЗ-03 клиентский кабинет: экраны входа/дел/карточки/согласий/оплат/результата + portal API.
- Решение по опыту DeepSeek: **не дообучать** модель на переписках; контур = обезличивание → кейсы → эксперт → RAG.
- В Agent mode реализованы реестр `knowledge/cases`, импорт, статусы качества, фильтр RAG, системный промпт помощника.
- CLI пакетного обезличивания: `sfrfr knowledge-depersonalize-dir inbox/ --out cleaned/`.
- ТЗ-09 этап C: ЮKassa в mini-app/cabinet, результат и сообщения, webhook статусов.
- Для пилота нужны 3–5 обезличенных экспортов диалогов (md/txt/json/html).

## Контекст

- Монетизация сопровождения пенсионного перерасчёта для инвалидов.
- Обращение в ZeroCoder: куратор + стратегия автоматизации.
- Запрос: структура папок, зависимости, окружение, Git, библиотеки.

## Решения

- Стек MVP: FastAPI + Supabase/Postgres + Tesseract OCR + LLM/RAG.
- Модель продукта: диагностика + сопровождение + success fee.
- B2C only: оферта + индивидуальный заказ; CRM Taganay; чек-листы индивидуально; Sheets без ПДн.
- Success fee: 10% ЕДВ + 50% от суммы прибавок за 3 месяца; постоплата через 2–3 месяца после повышения; 6 месяцев молчания → эскалация/суд (после юриста).
- AI: pipeline-оркестратор + узкие агенты (не swarm); сверка — детерминированный код.
- API/CLI завязаны на `CaseStore` + local upload + OCR при `advance`/`run`.
- Клиентский канал: MAX Bot API; LLM-провайдер: Yandex AI Studio.
- Витрина: WordPress на VPS; API на поддомене; DNS reg.ru.
- Сайт витрины: домен `https://taxi-doroga-dobra.ru/` (reg.ru) — **витрина и посадочная SFRFR**; на VPS в отдельной папке (не в `/opt/sfrfr`). API: `api.taxi-doroga-dobra.ru`.
- Витрина: тема Zakra + блоки; CTA MAX — заглушка `#` / «скоро» до появления deeplink.
- `PUBLIC_BASE_URL` на VPS: `https://api.taxi-doroga-dobra.ru`; `MAX_BOT_TOKEN` пока пуст → webhook не подписан.
- Публичный сайт ТЗ-02 этап 1: лендинг + оферта + ПДн/согласие + кнопка MAX + форма лида (WPForms, без сканов).
- Кабинет v1 мини-приложения: статус дела + загрузка документов; URL `https://taxi-doroga-dobra.ru/app/`; технический username бота `id8905998693_1_bot`.
- Кнопка на лендинге: «Открыть в MAX» → `https://max.ru/id8905998693_1_bot?startapp` (username из `/me`, не StazhIPensiyaBot).
