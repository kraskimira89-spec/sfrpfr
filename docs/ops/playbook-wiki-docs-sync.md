# Playbook: синк docs → Яндекс Wiki

**Дата:** 2026-09-22  
**Статус:** канон ops

## Цель

Перенести в Wiki (без сайта WP/кабинета и без ПДн):

- `docs/specs/` — ТЗ  
- `docs/ops/` — playbook’и и инструкции  
- `docs/history/` — опыт (кроме `conversation.md` / `project.md`)  
- `docs/marketing-sales/` — стратегии, playbook’и, отчёты  

Плюс хаб: [Инструкция сотруднику](https://wiki.yandex.ru/sfrfr/staff).

Канон остаётся в **git**. Wiki — удобный слой для людей.

## Команда

```bash
# план
sfrfr wiki-docs-sync --dry-run

# полный синк
sfrfr wiki-docs-sync

# проба
sfrfr wiki-docs-sync --limit 20
```

Env: `WIKI_TOKEN` (+ `TRACKER_ORG_ID`), уже на VPS.

## Slug’и

| Git | Wiki |
|-----|------|
| `docs/specs/01-architecture.md` | `/sfrfr/specs/01-architecture` |
| `docs/ops/playbook-….md` | `/sfrfr/ops/…` |
| `docs/history/2026-….md` | `/sfrfr/history/…` |
| `docs/marketing-sales/…` | `/sfrfr/marketing-sales/…` |

Индекс: https://wiki.yandex.ru/sfrfr/

## Sanitize

Email / телефон / СНИЛС / UUID / `y0_…` / cabinet URL → плейсхолдеры.  
Длинные страницы обрезаются (~48k) с пометкой «канон в git».

## Не синкаем

- HTML сайта, `scripts/assets/blog`, apps  
- `docs/history/conversation.md`, `project.md`  
- Секреты / `.env`
