# Технические задания SFRFR

Документация разделена по контурам продукта:

1. [01-architecture.md](01-architecture.md) — общая архитектура и границы систем.
2. [02-public-site-wordpress.md](02-public-site-wordpress.md) — публичный сайт WordPress.
3. [03-client-cabinet.md](03-client-cabinet.md) — клиентский кабинет.
4. [04-admin-cabinet.md](04-admin-cabinet.md) — кабинет оператора, эксперта и администратора.
5. [05-developer-operations.md](05-developer-operations.md) — инструменты разработчика и эксплуатация ([ранбук](../ops-runbook.md)).
6. [06-integrations-and-security.md](06-integrations-and-security.md) — интеграции, ПДн и правила доступа.
7. [07-mvp-roadmap.md](07-mvp-roadmap.md) — очередность MVP.
8. [08-knowledge-rag.md](08-knowledge-rag.md) — обезличенные кейсы, RAG без дообучения.
9. [09-client-channels-parity.md](09-client-channels-parity.md) — паритет MAX mini-app и веб-кабинета, выбор канала.
10. [10-landing-audit-and-implementation.md](10-landing-audit-and-implementation.md) — аудит и внедрение лендинга.
11. [11-blog.md](11-blog.md) — блог: SEO-справочник, рубрики, шаблон статей, CTA в каналы.
12. [12-amocrm.md](12-amocrm.md) — amoCRM: custom fields, sync лидов/этапов, CLI.  
    Пошаговая настройка UI: [../ops/amocrm-setup.md](../ops/amocrm-setup.md).
13. [13-document-ingest-v2.md](13-document-ingest-v2.md) — ingest документов: text layer / Vision / Tesseract, артефакты, HITL сверка.
14. [14-yandex-workspace.md](14-yandex-workspace.md) — Яндекс ID: почта, Телемост, календарь (аккаунт `proverkastaza@…`).  
    Настройка OAuth: [../ops/yandex-workspace-setup.md](../ops/yandex-workspace-setup.md).
15. [15-data-localization-ru.md](15-data-localization-ru.md) — локализация ПДн (152-ФЗ): MVP на Supabase Cloud, целевой self-hosted Supabase в Yandex Cloud + SmartCaptcha; план миграции.
16. [16-yandex-cloud-terraform.md](16-yandex-cloud-terraform.md) — Terraform staging в Yandex Cloud.
17. [17-management-analytics-russian-bi.md](17-management-analytics-russian-bi.md) — управленческая аналитика: **dbt marts → DataLens** (замена Google Sheets/Looker).  
    Cutover: [../ops/datalens-management-bi.md](../ops/datalens-management-bi.md).
18. [18-seo-strategy-and-implementation.md](18-seo-strategy-and-implementation.md) — SEO-стратегия: технический аудит, семантика, экспертный контент, аналитика и план на 6 месяцев.
19. [19-yandex-reviews-feedback.md](19-yandex-reviews-feedback.md) — сбор отзывов в Яндекс Бизнесе/Картах по правилам Яндекса (без накруток).  
    Ops: [../ops/yandex-business-reviews.md](../ops/yandex-business-reviews.md).
20. [20-max-private-chat-funnel.md](20-max-private-chat-funnel.md) — путь клиента: сайт → личный чат MAX → диагностика → защищённый кабинет документов.  
    Целевая эволюция (план): [../architecture/max-first-secure-pages.md](../architecture/max-first-secure-pages.md) — MAX-first, кабинет как страница действия после оплаты.
21. [21-trust-first-contact.md](21-trust-first-contact.md) — доверие на первом контакте: идентификация исполнителя, понятная цена и безопасная загрузка документов.
22. [22-trust-experience-awards.md](22-trust-experience-awards.md) — опыт и награды в блоке «Кто оказывает услугу» (слайдер с заглушкой до публикации фото).
23. [23-max-channel-promotion.md](23-max-channel-promotion.md) — оформление, запуск и продвижение канала MAX без смешения с личным чатом и кабинетом.
24. [24-max-client-boundaries-home.md](24-max-client-boundaries-home.md) — понятный блок на главной: канал MAX, личный чат и защищённый кабинет.
25. [25-max-ops-bot.md](25-max-ops-bot.md) — Ops-бот MAX «Проверка стажа-Ops» (`id8905998693_3_bot`, `MAX_OPS_BOT_TOKEN`) для лидов и approve staff.  
    Ops: [../ops/max-ops-bot-setup.md](../ops/max-ops-bot-setup.md).
26. [26-max-llm-chat.md](26-max-llm-chat.md) — черновик: ограниченный LLM-ответ на свободный текст в личном чате MAX (пока не к реализации).
27. [27-diagnosis-pdf-feedback.md](27-diagnosis-pdf-feedback.md) — обратная связь после PDF-диагностики: понятность и первый шаг, отдельно от публичного отзыва.
28. [28-diagnosis-secure-delivery.md](28-diagnosis-secure-delivery.md) — безопасная выдача PDF: draft-уведомления, сотрудник подтверждает, без вложений.
29. [29-diagnosis-surveys.md](29-diagnosis-surveys.md) — сервисные опросы после PDF (MAX clarity MVP; не маркетинг).
30. [30-diagnosis-delivery-triggers.md](30-diagnosis-delivery-triggers.md) — машина состояний и триггеры 1–4 (publish / approve / open / unread).
31. [31-email-delivery-webhooks.md](31-email-delivery-webhooks.md) — webhook доставки e-mail (канон: Yandex Cloud Postbox; резерв Postmark/Mailgun/SendGrid).
32. [32-customer-journey.md](32-customer-journey.md) — путь клиента: динамический чек-лист, сценарии, MAX consent-gate, банк staff-only, перенос трудовой.

## Принцип

WordPress — только маркетинг, правовые страницы и образовательный блог. Персональные данные, документы и работа по пенсионным делам обрабатываются только через отдельные защищённые кабинеты и API. Новые ТЗ сохранять в этой папке (`docs/specs/`).
