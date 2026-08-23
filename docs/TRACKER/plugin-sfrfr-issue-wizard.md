# Плагин «Мастер задач SFRFR» (`sfrfr-issue-wizard`)

Weavix-плагин для Яндекс Трекера: быстрое создание задач в очередях **STAZH** / **SFRFR** / **PUB** / **FUNNEL**.

## Параметры

| Поле | Значение |
|------|----------|
| Plugin ID / slug | `sfrfr-issue-wizard` |
| UI name | Мастер задач SFRFR |
| Слот | `navigation` |
| Категория | `productivity` |
| Support email | `bogdanchik2@yandex.ru` |
| Data permissions | `tracker:queues:read`, `tracker:issues:read`, `tracker:issues:write` |
| UI permissions | `toaster`, `confirm` |
| Путь | `plugins/tracker/sfrfr-issue-wizard/` |

Создан по шаблону Weavix CLI `@weavix/cli` (`navigation`), т.к. `weavix create` интерактивен (legal + checkbox).

## MVP

- Выбор очереди с краткой подсказкой (по умолчанию **STAZH**).
- Теги: **STAZH** → обязательный `type:*`; **PUB** → `publish-*`; **FUNNEL** → `funnel-*`; **SFRFR** → опционально `ops` / `infra` / `agents`.
- Prefill summary + description под очередь.
- Перед созданием: detect ПДн (телефон / email / СНИЛС) → `uiApi.confirm` + warn.
- Создание через `trackerApi.v3.post['/v2/issues']`, toast + `uiApi.navigate` на задачу.

Кабинет admin → STAZH (серверный API): [../ops/yandex-tracker-stazh-quality.md](../ops/yandex-tracker-stazh-quality.md).

## Отладка

```powershell
cd plugins\tracker\sfrfr-issue-wizard
npm install
weavix debug
```

В Трекере: **Настройки → Эксперименты → Отладка плагинов**. Плагин появляется в слоте navigation.

При необходимости: `weavix login` (OAuth + org id). Секреты только локально / `secrets/`, не в git.

## Сборка / публикация

```powershell
weavix build
# later: weavix login && weavix submit
```

См. также: [README плагинов](../../plugins/tracker/README.md), [playbook PUB](playbook-publish-queue.md), [playbook FUNNEL](playbook-funnel-ops.md).
