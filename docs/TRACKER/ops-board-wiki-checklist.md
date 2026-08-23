# Чеклист UI: доска и Wiki SFRFR

MCP **не** создаёт доски и страницы Wiki. Выполняет владелец (или агент с доступом к UI).

## Доска SFRFR

1. Открыть https://tracker.yandex.ru/SFRFR → Доски.
2. Создать / проверить доску **SFRFR**.
3. Колонки минимум: **Open → In Progress → Done**.
4. (Опционально) фильтры / отдельные представления:
   - **Publish** — теги `publish-max` OR `publish-vk` OR `publish-blog` OR `publish-seo` OR `publish-direct`
   - **Funnel** — теги `funnel-*` / компонент funnel
5. Типы задач: Task, Bug (Story по желанию) — уже скопированы с TRACKER при создании очереди.

## Wiki SFRFR

1. Создать раздел **SFRFR** в Яндекс Wiki.
2. Оглавление (страница-индекс) со ссылками:
   - git: `docs/TRACKER/README.md` (пакет агента)
   - git: `docs/ops/yandex-tracker-ops.md`
   - git: `docs/AMO/README.md`
   - git: `docs/marketing-sales/README.md`
   - git: `docs/VK/README.md`
3. Не импортировать Notion.
4. Не размещать ПДн, токены, полные `.env`.

## Критерий Done для seed-задач

- Доска видна команде; колонки работают.
- Wiki-индекс открывается; ссылки ведут на актуальные docs.
- В Трекере issues «Доска…» и «Wiki…» закрыты с комментарием «UI выполнен».
