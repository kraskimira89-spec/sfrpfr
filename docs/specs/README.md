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

## Принцип

WordPress — только маркетинг, правовые страницы и образовательный блог. Персональные данные, документы и работа по пенсионным делам обрабатываются только через отдельные защищённые кабинеты и API. Новые ТЗ сохранять в этой папке (`docs/specs/`).
