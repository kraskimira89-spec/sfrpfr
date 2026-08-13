# Playbook: дозаполнение Wordstat для 7 кластеров

Файл данных: [wordstat-7-clusters-template.csv](wordstat-7-clusters-template.csv)  
Research: [../research-seo-problem-clusters-wordstat-2026-08.md](../research-seo-problem-clusters-wordstat-2026-08.md)

## Шаги

0. **Через MCP (если подключён `yandex-wordstat` в Cursor):** спросить агента частоты по фразам из CSV — быстрее ручного кабинета. Ops: [../../ops/yandex-wordstat-mcp.md](../../ops/yandex-wordstat-mcp.md).
1. Открыть https://wordstat.yandex.ru/ (аккаунт Яндекса).
2. Регион: **Россия** → для каждой строки CSV колонка `query` снять «Частотность».
3. Вкладка «Похожие» — новые head-фразы добавить в CSV отдельной строкой (тот же `cluster`).
4. Гео (колонка `freq_geo`, формат `Москва:123; ЯНАО:45`):
   - Москва и область;
   - Санкт-Петербург и область;
   - ЯНАО / ХМАО (север);
   - один промышленный субъект по выбору.
5. Сохранить копию как `wordstat-7-clusters-filled-YYYY-MM-DD.csv` в этой папке (без ПДн).
6. Обновить research: заменить `TBD` на числа или приложить ссылку на filled CSV.

## Не делать

- Не коммитить скриншоты с личным аккаунтом/cookie.
- Не подставлять частоты «на глаз» в колонку `freq_rf` как факты.
