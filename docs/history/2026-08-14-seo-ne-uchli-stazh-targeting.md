# 2026-08-14 — SEO: статья «не учли стаж» под Wordstat

## Зачем
Яндекс вывел `/blog/chto-delat-esli-period-raboty-ne-uchten/` как малоценную/маловостребованную.
По [targeting](https://yandex.ru/support/webmaster/ru/recommendations/targeting.html) и [low-demand](https://yandex.ru/support/webmaster/ru/site-indexing/low-demand.html):
лексика страницы («период работы не учтён») не совпадала с запросами («не учли / не учтён стаж»).

## Что сделано
- `scripts/assets/blog/03-period-ne-uchten.html` — H1/лид/H2 под запросы Wordstat
- title/seo в `wp_seed_blog_tz11.php`, `sfrfr-seo-meta.php`, `wp_repair_seo_descriptions.php`
- позиция подачи: готовим план, подаёте сами, решение СФР

## После деплоя
1. Прогнать `wp_seed_blog_tz11` на VPS (обновит пост).
2. Переобход URL в Вебмастере.
