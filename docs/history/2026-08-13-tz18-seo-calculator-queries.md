# 2026-08-13 — ТЗ-18 пересмотр + семантика «калькулятор/расчёт»

## Что сделано

1. **ТЗ-18** (`docs/specs/18-seo-strategy-and-implementation.md`): статус v1.1 — этапы 0–3 внедрены, этап 4 в работе; baseline §3 разделён на исторический и фактический 2026-08.
2. **Ops этапа 4:** `seo-semantics-map`, `seo-sprint`, `seo-hypothesis-log`, `seo-webmaster-ui-checklist`; ссылки из `yandex-webmaster-setup` и `docs/marketing-sales/README.md`.
3. **Research:** `docs/marketing-sales/research-seo-pension-queries-2026-08.md` (кластеры A–F). Решение: **не** делать фейковый калькулятор выплат; ключи на существующих URL.
4. **Внедрение ключей (канон):**
   - Rank Math title/description в `scripts/wp_seed_blog_tz11.php` (ИЛС, сверка, FAQ);
   - H2/лиды в `01-ils-stazh.html`, `02-trudovaya-ils.html`, `09-faq-rasshirennyy.html`;
   - услуга: `wp_seed_trust_pages_tz18.php` + `trust/proverka-stazha.html`.
5. **Техпрогон:**
   - `seo_production_audit.py`: 45 страниц, **43 OK / 2 FAIL** (`/otzyvy/`, `/anketa-otzyv/` — два H1; вне scope калькуляторных ключей).
   - Вебмастер recrawl: услуга, ИЛС, сверка, FAQ, `/`, sitemap — OK (quota_left≈145).
   - Host diag (https apex): `searchable_pages_count=9`, `excluded_pages_count=3`, sitemap без ошибок; SQI=0.

## После деплоя кода

На VPS прогнать сиды блога/trust (если не входят в `deploy-vps`), иначе live meta/HTML останутся старыми до ручного `wp_seed_blog_tz11` / trust seed.

## Не делали

- Второй SEO-плагин, массовый reseed situations, отдельный URL-калькулятор выплат, этап 5.
