# 2026-08-03 — SEO недели 3–6: контент без раздувания

## Сделано

- Полная карта кластеров: `docs/ops/seo-url-decision-map.md` (ядро 15 + 30 thin).
- Pillar усилены вручную: ИЛС, сверка, неучтённый период, архив, подача, отказ; дата 03.08.2026.
- Hub «заказ ИЛС»: `kak-zakazat-vypisku-ils` (`21-zakazat-vypisku-ils.html`).
- 301 с `primer-*` / `analitika-*` → hub/pillar: MU `sfrfr-seo-redirects.php`.
- Север / ЕДВ / льготный hub’ы уже были — новых лишних не добавляли.

## Деплой

- `git push` → `deploy-vps.yml`
- На VPS: `wp_deploy_blog_ui.sh` + `wp_seed_blog_tz11.php`
- Recrawl изменённых URL в Вебмастере
