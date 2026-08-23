# Playbook: очередь публикаций

**Очередь Трекера:** **`PUB`** → https://tracker.yandex.ru/PUB

## Назначение

Планировать и закрывать слоты контента: MAX, VK, блог, SEO, Директ — с каноном подачи и без ПДн.

## Теги каналов (обязателен один)

| Тег | Канал |
|-----|--------|
| `publish-max` | MAX |
| `publish-vk` | ВКонтакте |
| `publish-blog` | блог proverkastaza.ru |
| `publish-seo` | SEO / семантика |
| `publish-direct` | черновики Директ (без секретов кабинета) |

Дополнительно: `marketing`.

## Статусы доски PUB

**Backlog / Draft / Ready / Published** — или Open / In Progress / Done + тег `ready-to-publish`.

## Шаблон задачи

**Summary:** `MAX: тема (слот YYYY-MM-DD)` — префикс `[PUB]` не обязателен (очередь уже PUB).

**queue:** `PUB`

```markdown
## Цель
…

## Канал и слот
- тег: publish-max | publish-vk | …
- дата слота: …

## Черновик
- git: `docs/…` / `scripts/assets/…`

## Чеклист
- [ ] people-first
- [ ] без перерасчёта / калькулятора
- [ ] без сканов в посте
- [ ] CTA канон подачи

## Done
Ссылка в комментарии; статус Done.
```

## Канон

- `scripts/assets/copy/submission-position.md`
- `docs/VK/playbook-vk-community.md`
- `docs/marketing-sales/`
