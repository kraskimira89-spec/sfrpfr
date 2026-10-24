# Индекс документации об ошибках ИИ / сервиса

**Координация:** SFRFR-100 · **диалоговая волна:** SFRFR-110  
**Статус:** только спецификация. Live-приёмка — отдельно.

Этот файл — **вход в docs-пакет ошибок** (PR #262). Он **не** заменяет полный каталог сценариев 20.x.

## Сверка с PR #261 (`client-ai-dialogue-quality.md`)

| Файл | Владелец | Правило merge |
|---|---|---|
| `client-ai-dialogue-quality.md` | **SFRFR-110 / PR #261** — полный корпус § и сценариев | При конфликте путей **сохранить содержимое #261**; не затирать каталог 20.x |
| `client-ai-error-docs-index.md` (этот файл) | PR #262 | Индекс ссылок на канон ошибок |
| `client-ai-error-response-catalog.md` и др. ниже | PR #262 | SoT текстов/переходов/evidence по ошибкам |

После слияния обоих PR в `quality.md` (#261) добавить **короткий блок ссылок** на таблицу SoT ниже — без копирования полных правил.

## Источники истины (ошибки)

| Тема | Канон | Не дублировать |
|---|---|---|
| Тексты при ошибке | [`client-ai-error-response-catalog.md`](client-ai-error-response-catalog.md) | длинные копипасты в ops message-catalog |
| Контракты переходов | [`client-ai-transition-contracts.md`](client-ai-transition-contracts.md) | те же запреты вторым реестром |
| Доказательства | [`client-ai-evidence-requirements.md`](client-ai-evidence-requirements.md) | конкурирующий «evidence registry» |
| QA | [`../qa/client-ai-error-scenarios.md`](../qa/client-ai-error-scenarios.md) | прод-данные |
| Пробелы кода | [`../ops/client-ai-error-implementation-gaps-2026-10-24.md`](../ops/client-ai-error-implementation-gaps-2026-10-24.md) | объявлять live «готовым» |

## Принцип

Исправление подтверждается действиями и событиями, не извинением.

```text
Тип ошибки + подтверждённое состояние + проверенные последствия
+ фактически выполненные действия → клиентский текст
```

## Границы

- Без миграций, live-handler, тарифов и юробещаний в этом контуре.
- Auto-merge OFF; merge вручную после ревью.
