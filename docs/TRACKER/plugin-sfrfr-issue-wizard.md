# Плагин «Мастер задач SFRFR» (`sfrfr-issue-wizard`)

Weavix-плагин для Яндекс Трекера: быстрое создание задач в очередях **SFRFR** / **PUB** / **FUNNEL**.

## Параметры

| Поле | Значение |
|------|----------|
| Plugin ID / slug | `sfrfr-issue-wizard` |
| Platform Plugin ID | `07376a90-6b90-43fb-81d7-21f77d3baf1d` |
| UI name | Мастер задач SFRFR |
| Слот | `navigation` |
| Категория | `productivity` |
| Support email | `bogdanchik2@yandex.ru` |
| Data permissions | `tracker:queues:read`, `tracker:issues:read`, `tracker:issues:write`, `tracker:tags:read` |
| UI permissions | `toaster`, `confirm` |
| Путь | `plugins/tracker/sfrfr-issue-wizard/` |
| Version | `0.1.6` (на модерации после `weavix submit`) |

Создан по шаблону Weavix CLI `@weavix/cli` (`navigation`): `weavix create` интерактивен (legal + checkbox), поэтому scaffold скопирован из шаблона CLI.

## MVP

- Выбор очереди с краткой подсказкой.
- Теги: **PUB** → обязательный `publish-*`; **FUNNEL** → обязательный `funnel-*`; **SFRFR** → опционально `ops` / `infra` / `agents`.
- Prefill summary + description под очередь.
- Перед созданием: detect ПДн (телефон / email / СНИЛС) → `uiApi.confirm` + warn.
- Создание через `trackerApi.v3.post['/issues']` (как в [примерах](https://yandex.ru/support/tracker/ru/plugins/examples.md); путь `/v2/issues` даёт ошибку scope `tracker:v2:write`), toast + `uiApi.navigate` на задачу.

## Отладка

```powershell
cd plugins\tracker\sfrfr-issue-wizard
npm install
weavix debug
```

В Трекере: **Настройки → Эксперименты → Отладка плагинов**. Плагин появляется в слоте navigation.

`downloadUrl` в локальном `config.json` (не в git) обычно `http://localhost:5173`.

Если видите `missing required scope: tracker:v2:write` — в коде должен быть путь **`/issues`**, не `/v2/issues`. Разрешение в манифесте: `tracker:issues:write` ([common.md §permissions](https://yandex.ru/support/tracker/ru/plugins/common.md#permissions)).

При необходимости publish: `weavix login` (OAuth + org id). Секреты только локально / `secrets/`, не в git.

## Сборка / публикация (каталог организации)

По [доке](https://yandex.ru/support/tracker/ru/plugins/publish.md): ассеты → `weavix login` → `weavix submit` → модерация → одобрение админом org.

| Поле | Значение |
|------|----------|
| Version | `0.1.6` |
| Platform Plugin ID | `07376a90-6b90-43fb-81d7-21f77d3baf1d` |
| Visibility (ожидаемо) | `ORGANIZATION` |
| Marketplace | `marketplace/index.md`, `marketplace/header-image.jpg`, `public/logo.svg` |
| Справка | `docs/index.md` + `docs/toc.yaml` |

В манифесте поле `id` — **UUID платформы** (не slug). Если указать slug в `id`, `weavix submit` пойдёт в update и упадёт с `expected type: UUID`. Первая публикация: без `id` → CLI создаёт плагин и сам проставляет UUID.

```powershell
cd plugins\tracker\sfrfr-issue-wizard
npm install
weavix doctor --publish
weavix build
# токен уже в Credential Store после weavix login
weavix submit
weavix list
weavix info
```

После `IN_REVIEW` → каталог: **Настройки → Плагины**. Админ одобряет запрос на подключение. В общий публичный каталог Трекера — только через [поддержку](https://yandex.ru/support/tracker/ru/feedback.md) + архив исходников.

Секреты / OAuth не коммитить. `paths-ignore`: пуш плагина не деплоит VPS.

См. также: [README плагинов](../../plugins/tracker/README.md), соседний [stazh-quality-wizard](plugin-stazh-quality-wizard.md) (уже `DRAFT` / submit).
