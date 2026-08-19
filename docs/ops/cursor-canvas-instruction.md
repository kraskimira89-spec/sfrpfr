# Cursor Canvas: инструкция для проекта SFRFR

**Дата:** 2026-08-19  
**Назначение:** как открывать, хранить и эффективно использовать Canvas в Cursor рядом с чатом.

---

## Что такое Canvas

Canvas — **живой React-артефакт** (один файл `.canvas.tsx`), который Cursor компилирует и показывает **рядом с чатом**. Это не страница сайта и не файл деплоя на VPS.

Подходит для: таблиц Wordstat, матриц гео, cost breakdown, аудитов, сравнений, схем с данными.

Не подходит для: правок HTML/PHP блога, PR, деплоя, коротких ответов в чате.

Канон skill агента: `~/.cursor/skills-cursor/canvas/SKILL.md`.

---

## Где хранятся файлы

Canvas **не лежат в git-репозитории** `SFRFR`. Они в управляемой папке Cursor для этого workspace:

```text
C:\Users\user\.cursor\projects\c-Users-user-Documents-Cursor-SFRFR\canvases\
```

### Правила пути

| Правило | Детали |
|---|---|
| Только эта папка | IDE подхватывает canvas **только** из `canvases/` |
| Без подпапок | `canvases/reports/foo.canvas.tsx` **не** откроется как canvas |
| Расширение | строго `*.canvas.tsx` |
| Один файл | один canvas = один файл, без helper-модулей |

### Примеры в этом проекте

| Файл | Зачем |
|---|---|
| `wordstat-north-promo-site.canvas.tsx` | северная матрица / промо |
| `yc-vs-regru-cost.canvas.tsx` | сравнение YC vs REG.RU ([yc-cost-breakdown-vs-regru.md](yc-cost-breakdown-vs-regru.md)) |

В репо можно **ссылаться** на canvas в `docs/` (путь + имя файла), но сам `.canvas.tsx` остаётся в `.cursor/projects/.../canvases/`.

---

## Как открыть

1. Открыть файл из `canvases/` в Explorer (или клик по ссылке в ответе агента).
2. Cursor покажет превью **рядом с чатом**.
3. После правок в файле — сохранить; превью обновится.

---

## Когда просить Canvas у агента

**Да:**

- отчёты Wordstat, гео-матрицы, кластеры;
- сравнение тарифов / инфраструктуры;
- таблицы на десятки строк, где данные — главный результат;
- интерактивные сводки по MCP (Datadog, Wordstat и т.п.).

**Нет:**

- правка лендинга, seed WP, коммит/деплой;
- «напиши статью в HTML»;
- однострочный ответ или один diff.

**Формулировка:** «Сделай canvas …» / «Вынеси в canvas таблицу …».

---

## Как работать эффективно

### 1. Давать данные в запросе

В canvas **нет `fetch()`** — данные вшиваются в файл. Прикладывайте CSV, цифры, списки URL — меньше итераций.

### 2. Именовать по смыслу

Хорошо: `wordstat-north-promo-site.canvas.tsx`  
Плохо: `report1.canvas.tsx`

### 3. Дорабатывать тот же файл

«Добавь колонку ЯНАО», «фильтр P0» — правки в **существующем** `.canvas.tsx`, не копии.

### 4. Canvas + docs

| Где | Роль |
|---|---|
| Canvas | интерактив / таблица для работы в IDE |
| `docs/marketing-sales/reports/` | канон в git для команды и деплоя |

### 5. Ограничения SDK (чтобы не ломалось)

- импорт **только** из `cursor/canvas`;
- **default export** одного компонента;
- цвета через `useHostTheme()`, без hardcoded hex;
- без градиентов, box-shadow, emoji как декора;
- компоненты: `Table`, `BarChart`, `LineChart`, `Card`, `CollapsibleSection`, `Stat`, `Grid` — см. `~/.cursor/skills-cursor/canvas/sdk/index.d.ts`.

---

## Шаблон запроса агенту

```text
Сделай canvas: canvases/wordstat-ne-uchli-matrix.canvas.tsx

Содержание:
- таблица: кластер | URL live | commercial | частота RF | статус
- данные из docs/marketing-sales/reports/wordstat-7-clusters-filled-2026-08-14.csv
  (строки 1_ne_uchli, 3_arhiv, 5_otkaz)
- секция «live» vs «gap»
```

---

## Если canvas пустой

1. Проверить путь: файл **прямо** в `...\canvases\имя.canvas.tsx`.
2. Расширение `.canvas.tsx`, не `.tsx`.
3. Посмотреть в tool result строку **Canvas TypeScript check** — там ошибки типов.

---

## Связанные материалы в репо

- [seo-semantics-map.md](seo-semantics-map.md) — URL live vs candidate
- [yandex-wordstat-setup.md](yandex-wordstat-setup.md) — Wordstat API / MCP
- [blog-targeting-audit-2026-08-14.md](../marketing-sales/reports/blog-targeting-audit-2026-08-14.md) — targeting блога

---

## Кратко

Canvas = доска в `.cursor/projects/.../canvases/`, открывается рядом с чатом. Для сайта и SEO — git + Agent mode; для сводок и матриц — canvas + явный запрос с данными.
