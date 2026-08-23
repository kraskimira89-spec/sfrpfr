# Playbook: жизненный цикл задачи агента

**Очереди:** `SFRFR` · `PUB` · `FUNNEL`

## Выбор очереди

| Работа | Очередь |
|--------|---------|
| Код, деплой, infra, Wiki, agents | **SFRFR** |
| Пост, статья, SEO-слот | **PUB** |
| Ops воронки, SLA, LOSS, чеклисты этапов | **FUNNEL** |

## Цикл

```text
issues_find (нужная Queue)
  → issue_create (queue=SFRFR|PUB|FUNNEL)
  → In Progress
  → issue_add_comment
  → Done
```

## Шаблоны summary

| Очередь | Пример |
|---------|--------|
| SFRFR | `[OPS] Деплой: проверить deploy-vps` |
| PUB | `MAX: слот недели (шаблон)` |
| FUNNEL | `SLA ответа на lead/qualify` |

## Комментарий при закрытии

Что сделано, пути файлов, commit — без секретов и ПДн.
