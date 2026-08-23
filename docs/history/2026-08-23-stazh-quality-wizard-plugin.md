# 2026-08-23 — Weavix-плагин stazh-quality-wizard

## Что

Новый плагин Яндекс Трекера `plugins/tracker/stazh-quality-wizard` для очереди **STAZH**:
типы качества, теги `type/dir/src/ch/rep`, блок запрета ПДн, жёсткий детект ПДн (блок создания).

## Зачем

Отделить ручное создание задач качества в Tracker UI от мастера SFRFR/PUB/FUNNEL и от
серверного MVP admin → Tracker API.

## Документация

- `docs/TRACKER/plugin-stazh-quality-wizard.md`
- `plugins/tracker/README.md`

## Publish 0.1.1 (follow-up)

- Platform ID `654059d7-7712-44fa-bbab-62dc0d132acb`
- Status: plugin `DRAFT`, version `IN_REVIEW`, visibility `ORGANIZATION`
- Submit commits: `1626e42`, `2adeaf0`; Tracker: [STAZH-2](https://tracker.yandex.ru/STAZH-2)
- Debug port: `5174`; команды: `weavix build` / `weavix submit`
