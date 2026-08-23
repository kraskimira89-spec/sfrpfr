# Плагин «Качество STAZH» (`stazh-quality-wizard`)

Weavix-плагин для Яндекс Трекера: создание **обезличенных** внутренних задач в очереди **STAZH**.

Связан с MVP кабинета: [../ops/yandex-tracker-stazh-quality.md](../ops/yandex-tracker-stazh-quality.md).  
Соседний плагин (SFRFR/PUB/FUNNEL): [plugin-sfrfr-issue-wizard.md](plugin-sfrfr-issue-wizard.md).

## Параметры

| Поле | Значение |
|------|----------|
| Plugin ID / slug | `stazh-quality-wizard` |
| UI name | Качество STAZH |
| Слот | `navigation` |
| Категория | `productivity` |
| Support email | `bogdanchik2@yandex.ru` |
| Data permissions | `tracker:queues:read`, `tracker:issues:read`, `tracker:issues:write` |
| UI permissions | `toaster`, `confirm` |
| Путь | `plugins/tracker/stazh-quality-wizard/` |
| Debug port | `5174` (отдельно от мастера SFRFR на 5173) |

## MVP

- Очередь фиксирована: **STAZH**.
- Тип задачи → тег `type:*` (bug, sla_incident, channel_conflict, …).
- Направление / источник / канал / повторяемость → теги `dir:*`, `src:*`, `ch:*`, `rep:*` + `quality`, `stazh`.
- Приоритет → поле Tracker (`critical` / `normal` / `minor`).
- Prefill описания без ПДн.
- Красный блок-предупреждение про запрет ПДн.
- Детект ПДн (телефон, email, СНИЛС, UUID, cabinet/admin URL) — **блокирует** создание (не «всё равно»).
- Создание через `trackerApi.v3.post['/v2/issues']`, toast + переход к задаче.

Клиентские дела и `case_ref` из карточки — через admin API; этот плагин — для ручного заведения задач сотрудником прямо в Tracker.

## Отладка

```powershell
cd plugins\tracker\stazh-quality-wizard
npm install
weavix debug
```

В Трекере: **Настройки → Эксперименты → Отладка плагинов** — подключить локальный плагин (обычно `http://localhost:5174`).

## Сборка

```powershell
weavix build
# later: weavix login && weavix submit
```

## Публикация (каталог)

| Поле | Значение |
|------|----------|
| Platform Plugin ID | `654059d7-7712-44fa-bbab-62dc0d132acb` |
| Slug | `stazh-quality-wizard` |
| Version submitted | `0.1.1` |
| Status after submit | `DRAFT` (на модерации) |
| Org | из `weavix login` / `~/.yaweavix/config.json` (`api.platformOrgId`) |

`powershell
cd plugins\tracker\stazh-quality-wizard
npm install
weavix doctor
weavix build
# первый submit: в manifest не должно быть id=slug — CLI создаст UUID и запишет в manifest.id
weavix login   # OAuth + Organization ID (Windows Credential Store + ~/.yaweavix)
weavix submit
weavix list
weavix info
`

Каталог в UI Трекера: **Настройки → Плагины / Каталог плагинов** (после модерации статус сменится с DRAFT).

Marketplace-ассеты обязательны: `marketplace/index.md`, `marketplace/header-image.jpg`, `public/logo.svg`.
Permissions v2: `tracker.v2.read` / `tracker.v2.write` (точки, не `tracker:v2:*`).
