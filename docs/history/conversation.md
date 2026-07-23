# История беседы (кратко)

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
- MAX-бот «Стаж и пенсия»: токен на VPS, webhook подписан (`success: true`). Username API: `id8905998693_1_bot`.
- Кабинет v1 мини-приложения: статус дела + загрузка документов; URL `https://taxi-doroga-dobra.ru/app/`; технический username бота `id8905998693_1_bot`.
- Кнопка на лендинге: «Открыть в MAX» → `https://max.ru/id8905998693_1_bot?startapp` (username из `/me`, не StazhIPensiyaBot).
