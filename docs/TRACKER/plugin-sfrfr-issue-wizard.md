# Плагин «Мастер задач SFRFR» (`sfrfr-issue-wizard`)

Weavix-плагин для Яндекс Трекера: быстрое создание задач в очередях **SFRFR** / **PUB** / **FUNNEL**.

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

## Сборка / публикация

```powershell
weavix build
# later: weavix login && weavix submit
```

См. также: [README плагинов](../../plugins/tracker/README.md), [playbook PUB](playbook-publish-queue.md), [playbook FUNNEL](playbook-funnel-ops.md).
