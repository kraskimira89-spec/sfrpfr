# Маркетинг и продажи «Проверки стажа»

Единая папка для стратегии, исследований, технических заданий, каналов продвижения, продаж и будущего корпоративного направления (B2B).

## Документы

- [Стратегия маркетинга и продаж 2026–2028](strategy-2026-2028.md) — аудитории, позиционирование, каналы, розничная воронка (B2C) и переход к корпоративным продажам (B2B).
- [ТЗ на реализацию стратегии](spec-marketing-sales-foundation.md) — аналитика, посадочные страницы, реклама, система продаж (CRM), MAX и исследование корпоративных потребностей (B2B discovery).
- [ТЗ чата «Маркетинг» (агент)](spec-marketing-agent-chat.md) — режимы работы, границы, P0 без бюджета, без поломки сайта.
- [Пакет агента «Маркетолог»](Marketing/README.md) — промпт, роль, чеклист P0, шаблоны гипотез и постов.
- [Промпт агента «Маркетолог»](Marketing/prompt-agent-marketer.md) — скопировать в новый чат Cursor.
- [Промпт чата «Маркетинг» (legacy-ссылка)](prompt-agent-marketing.md) — перенаправляет в пакет Marketing.
- [Исследование аудитории и каналов](research-audience-channels-2026-08.md) — исходные данные, ограничения и источники.
- [План 1 000 подписчиков в MAX (Launchi)](research-launchi-max-1000-subscribers.md) — конспект статьи с раскрытыми блоками + адаптация под SFRFR.
- [Контент-план канала MAX (ежедневно с 22.08.2026)](playbook-max-channel-month-2026-08.md) — очередь + блок «что будет после кнопки»; cron → ops.
- [Цифровой ID MAX для SFRFR](research-max-digital-id-for-sfrfr.md) — выжимка API age-verification / `pensioner`, границы внедрения (кабинет, не чат).
- [Сегмент «Северный стаж»](research-segment-north-2026-08.md) — формула, сообщения v2, 5 постов MAX, 5 гипотез с UTM.
- [Сегмент «Родственники»](research-segment-relative-2026-08.md) — рабочий лист, рядом/вместе, гипотезы.
- [Сегмент «Перед пенсией»](research-segment-pre-retirement-2026-08.md) — рабочий лист, сверка заранее, гипотезы.
- [Тест Ноябрьск × север × Директ](research-test-noyabrsk-north-direct-2026-08.md) — одностраничный план (бюджет TBD).
- [**Директ: копипаст объявлений + минус-слова**](spec-yandex-direct-copypaste.md) — 2 кампании (север волна 1 + 5 кластеров РФ), UTM, гео ID.
- [Лид-магнит «4 проверки»](research-leadmagnet-4-proverki-stazha-2026-08.md) — пост/карточка без обещания денег.
- [SEO: запросы «калькулятор/расчёт пенсии/стаж»](research-seo-pension-queries-2026-08.md) — кластеры, интенты, внедрение ключей без фейкового калькулятора выплат; [частоты 8_calc](reports/wordstat-8-calc-2026-08-14.md).
- [SEO: 7 проблемных кластеров Wordstat](research-seo-problem-clusters-wordstat-2026-08.md) — не учли ИЛС, до 2002, архив, север, отказ, СЗИ-ИЛС, перед пенсией; маппинг URL/Title/H1/CTA; [CSV](reports/wordstat-7-clusters-template.csv), [playbook](reports/playbook-wordstat-7-clusters.md), [Wordstat API](../ops/yandex-wordstat-setup.md).
- [Wordstat: север × пенсионеры × АЗРФ/КС](reports/wordstat-north-pensioners-2026-08-14.md) — обход регионов Арктики, Крайнего Севера и приравненных; [JSON регионов](reports/wordstat-north-regions.json).
- [Рекомендации сайт + продвижение по северной матрице](reports/wordstat-north-actions-2026-08-15.md) — P0/P1 после полного обхода 13×22.
- [Статус реализации](reports/2026-08-09-implementation-status.md) — что сделано в коде и что BLOCKED у владельца.
- Playbook’и: [**ясность / воронка / возражения**](playbook-sales-clarity-funnel.md), [квалификация](playbook-sales-qualification.md), [**marketing consent MAX**](playbook-marketing-consent.md), [редактура](playbook-editorial-standard.md), [партнёры](playbook-partner-onepager.md), [посадочная `/partneram/`](playbook-partneram-page.md), [обратная связь CF7](playbook-site-feedback-cf7.md), [Простой старт Директ](playbook-yandex-direct-simple-start.md), [трудовая → таблица Word](playbook-trudovaya-word-table.md), [карточка Яндекс Бизнес](playbook-yandex-business-card.md), [Яндекс Форма к отзыву](playbook-yandex-form-review-prompts.md).
- Чек-лист самопомощи ИЛС (MAX): [`scripts/assets/copy/ils-self-check-checklist.md`](../../scripts/assets/copy/ils-self-check-checklist.md) — первый безопасный шаг, не утешительный приз.
- Диагностика → оплата (без давления): [`scripts/assets/copy/diagnosis-offer-to-payment.md`](../../scripts/assets/copy/diagnosis-offer-to-payment.md) — §4б clarity-funnel.
- После оплаты → результат: [`scripts/assets/copy/diagnosis-result-delivery.md`](../../scripts/assets/copy/diagnosis-result-delivery.md) — §4в (срок, каркас, оффер 5k/8k).
- **amoCRM (чат AMO):** [`docs/AMO/`](../AMO/README.md) — ТЗ-12, ops, QA, промпт агента.
- **Задачи и wiki (Notion не используем):** Яндекс Трекер (очередь `SFRFR`) + MCP [yandex-tracker-mcp](../ops/yandex-tracker-mcp.md); Wiki SFRFR; SoT — [yandex-tracker-ops.md](../ops/yandex-tracker-ops.md).
- **Стек автоматизации (без Make/Albato):** [`docs/ops/automation-stack-ru.md`](../ops/automation-stack-ru.md) — лиды, amo, AI, n8n P2.
- **ВКонтакте (чат VK):** [`docs/VK/`](../VK/README.md) — сообщество, ритм/CTA/лид-форма/UTM под тарифы 3/5/8, обзор API, промпт агента.
- **Бренд и визуализация смыслов:** [`docs/brand/`](../brand/README.md) — миссия, ценности, ассоциации, брифы на символы. Чат бренда: [`prompt-agent-brand-rollout.md`](../brand/prompt-agent-brand-rollout.md).

## Правила хранения

Новые материалы размещать здесь:

- `strategy-*.md` — стратегии;
- `spec-*.md` — технические задания;
- `research-*.md` — исследования и проверка гипотез;
- `playbook-*.md` — инструкции по каналам и продажам;
- `reports/` — результаты рекламных тестов и ежемесячные отчёты.
- [Контроль воронки MAX](reports/max-funnel-control.md) — еженедельная таблица на Яндекс Диске (`SFRFR-ops/marketing-max-funnel`).
- [Аудит кнопок CTA](research-cta-buttons-audit-2026-08.md) — разнообразие primary/secondary, канон «одно действие».
- [Поток отзыва: анкета → ИИ → Яндекс](research-review-ai-draft-flow-2026-08.md) — целевой UX после completed.

Не хранить в папке персональные данные, выгрузки клиентов, рекламные токены, ключи и пароли.

Английские названия файлов и технические идентификаторы сохранять только там, где они нужны системе. В тексте сначала использовать русский термин, а английский эквивалент указывать в скобках при первом употреблении.

## Обязательная позиция сервиса

> Мы готовим документы, проект обращения и понятный план. Мы расскажем по шагам, но обращение через СФР, МФЦ или Госуслуги подаёте вы сами. Решение о пенсии и перерасчёте принимает только СФР.

Эталон: `scripts/assets/copy/submission-position.md`.

## Источники истины и приоритет документов

При расхождении документов применять следующий порядок:

1. **Позиция о подаче:** `scripts/assets/copy/submission-position.md`.
2. **Публичные цены:** опубликованные `scripts/assets/trust/tarify.html`, главная страница и `scripts/assets/yandex-business/price-list.yml`. Сейчас это поэтапно **3 000 ₽ / 5 000 ₽ / 8 000 ₽** (диагностика → подготовка документов → сопровождение до подачи) и доп. перенос трудовой в Word — **100 ₽ за разворот**.
3. **Путь через MAX:** ТЗ-20, ТЗ-21 и ТЗ-24 новее ТЗ-10. Документы принимаются только в защищённом кабинете, а не в канале или личном чате.
4. **Данные дела и оплаты:** приложение SFRFR — источник истины; amoCRM ведёт продажи и задачи, но не хранит файлы дела.
5. **Управленческая аналитика:** модели dbt и Яндекс DataLens. Таблицы допустимы только как временная обезличенная выгрузка.
6. **Вознаграждение за подтверждённый результат:** ранняя модель и договоры считаются черновиками до единого решения владельца и юридической проверки.
7. **Яндекс Бизнес:** единая карточка `82469923047` (4 позиции = YML/сайт); дубликат удалён. Форма отзывов и QR на этот ID. См. `docs/ops/yandex-business-profile.md`.

Если цена, роль канала или юридическая формулировка расходятся, рекламу и публикацию останавливают до устранения расхождения.

## Единые термины

- розничное направление (B2C);
- корпоративное направление (B2B);
- профиль идеального клиента (ICP);
- исследование потребностей (discovery);
- партнёр пилотного проекта (design partner);
- работа под брендом партнёра (white-label);
- изолированный контур организации (tenant);
- исходные показатели (baseline);
- призыв к действию (CTA);
- вознаграждение за подтверждённый результат (success fee);
- поисковая оптимизация (SEO);
- норматив времени ответа (SLA);
- стоимость привлечения клиента (CAC).

## Связанный продуктовый контекст

- `docs/specs/18-seo-strategy-and-implementation.md`
- `docs/specs/17-management-analytics-russian-bi.md`
- `docs/specs/20-max-private-chat-funnel.md`
- `docs/specs/21-trust-first-contact.md`
- `docs/specs/23-max-channel-promotion.md`
- `docs/specs/24-max-client-boundaries-home.md`
- `docs/strategy/client-journey-max.md`
- `docs/b2c-customer-journey.md`
- `docs/b2c-monetization-tz.md`
- `docs/b2c-monetization-model.md`
- `docs/ops/yandex-business-profile.md`
- `.cursor/rules/blog-manual-only.mdc`
