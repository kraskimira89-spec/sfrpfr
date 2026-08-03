# Страницы доверия и коммерции (ТЗ-18, недели 2–3)

Дата: 2026-08-03

## URL

| URL | Назначение |
|---|---|
| `/proverka-stazha/` | услуга |
| `/tarify/` | тарифы |
| `/kak-rabotaem/` | процесс |
| `/kontakty/` | контакты + реквизиты |
| `/expert/lopakova-nataliya/` | кто оказывает / автор-проверяющий |

Сидер: `scripts/wp_seed_trust_pages_tz18.sh`

## Авторство статей

- meta `_sfrfr_author_name`, `_sfrfr_author_url`, `_sfrfr_reviewer_name`
- byline + Article.author=Person в `sfrfr-seo-meta.php`
- без неподтверждённых квалификаций («юрист», «пенсионный эксперт»)

## Метрика

Цели без ПДн (после consent): `lead_ok`, `lead_start`, `max_click`, `cabinet_click`, `tariff_view`, `form_error`.  
`tariff_view` срабатывает на `#tarify` и на `/tarify/`.
