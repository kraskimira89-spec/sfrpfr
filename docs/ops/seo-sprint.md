# Ежемесячный SEO-спринт (ТЗ-18 §17)

**Канон:** [ТЗ-18](../specs/18-seo-strategy-and-implementation.md)  
**Журнал:** [seo-hypothesis-log.md](seo-hypothesis-log.md)  
**Семантика:** [seo-semantics-map.md](seo-semantics-map.md)  
**UI Вебмастера:** [seo-webmaster-ui-checklist.md](seo-webmaster-ui-checklist.md)

## Технический контур (еженедельно, CI)

Workflow: `.github/workflows/seo-production-audit.yml` (пн) → `python scripts/seo_production_audit.py`.  
Ручной прогон: `python scripts/seo_production_audit.py --base-url https://proverkastaza.ru`.

## Ежемесячный спринт (чеклист)

1. Выгрузить Вебмастер (запросы, страницы в поиске, диагностика) — хост **без www**.
2. Выгрузить Метрику: органика → CTA → заявка (цели без ПДн).
3. Выгрузить Google Search Console (индекс / запросы).
4. Просмотреть `seo_production_audit` / последний CI run.
5. Выбрать **максимум 3–5 гипотез** → записать в [seo-hypothesis-log.md](seo-hypothesis-log.md).
6. Для каждой: URL, интент, изменение, метрика успеха, срок пересмотра.
7. Внедрить (мета/контент/перелинковка) → `yandex_webmaster_recrawl.py` на изменённые URL.
8. Техэффект — сразу; поисковый — после разумного переобхода (неделя+).
9. Решение: оставить / доработать / откатить / проверить позже.
10. Обновить [seo-semantics-map.md](seo-semantics-map.md) при новых кластерах.

## Правила

- Не гарантировать TOP-10 и число заявок.
- Один интент — один основной URL.
- Не создавать фейковый калькулятор выплат.
- Без ПДн в отчётах и UTM.
