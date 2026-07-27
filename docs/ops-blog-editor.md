# Инструкция редактора: блог «Проверка стажа»

См. ТЗ: [docs/specs/11-blog.md](../specs/11-blog.md).

## Публикация новой статьи

1. В WordPress: **Записи → Добавить**.
2. Заголовок — вопрос читателя (как в поиске), один H1.
3. Рубрика: ИЛС / Стаж / Документы / Подача / Для родственников / Услуга.
4. Структура текста (шаблон ТЗ-11 §4): короткий ответ → кому полезна → шаги → документы → ошибки → когда обратиться → CTA.
5. В конце статьи вставьте блок CTA на `/#kak-rabotat` и дисклеймер:

> Не являемся СФР. Решение о перерасчёте принимает СФР. Материал носит справочный характер.

6. Title и description (Rank Math / SEO-плагин) — уникальные, без «гарантируем» / «официально от СФР».
7. Статус: **Опубликовано**. URL статьи: `/blog/slug/`. Рубрики: `/blog/rubrika/{slug}/` (не `/blog/{рубрика}/` — иначе 404 у постов).

## Обновление статьи

1. Правьте текст и дату обновления (в SEO-плагине или вручную в начале: «Обновлено: ДД.ММ.ГГГГ»).
2. Проверьте ссылки на Госуслуги / СФР / МФЦ.
3. Раз в ~6 месяцев — плановый просмотр статей о подаче и отказах (с экспертом).

## Запрещено

- Обещать перерасчёт, сумму, «100%».
- Upload документов в формах WP.
- ФИО, кейсы с ПДн, печати/гербы СФР.
- Комментарии к постам (сид закрывает `comment_status` и `default_comment_status`).

## Sitemap

Rank Math обычно отдаёт:

- `https://proverkastaza.ru/sitemap_index.xml`
- или `https://proverkastaza.ru/sitemap.xml`

Если 404 — в WP: Rank Math → Sitemap Settings → включить sitemap и сбросить permalinks.

## Сид с сервера

Первичный набор статей:

```bash
SITE_DIR=/var/www/taxi-doroga-dobra bash /opt/sfrfr/scripts/wp_seed_blog_tz11.sh
```

После правок главной (`sfrfr-home.html`) — обычный `wp_seed_site_tz02.sh` или `wp_apply_home.php`.

## UI §13 (чипы / TOC / CTA)

Спека: [docs/specs/11-blog.md](../specs/11-blog.md) §13. Файлы:

- `scripts/wp-mu-plugins/sfrfr-blog-ui.php`
- `scripts/assets/blog/ui/blog-ui.css`
- `scripts/assets/blog/ui/blog-ui.js`

Выкат на VPS (после `git pull` в `/opt/sfrfr`):

```bash
sudo bash /opt/sfrfr/scripts/wp_deploy_blog_ui.sh
# при другом пути к WP:
# WP_CONTENT=/var/www/SITE/wp-content sudo -E bash /opt/sfrfr/scripts/wp_deploy_blog_ui.sh
```

Проверка:

1. `/blog/` — чипы рубрик + один CTA «Начать проверку».
2. Статья — блок «Содержание» (если ≥2 заголовка), CTA mid/end, «Похожие статьи».
3. Главная — блок из 3 карточек (сид ТЗ-11), без обязательного CTA блока.

Smoke:

```bash
curl -sI https://proverkastaza.ru/blog/ | head -n1
curl -sI https://taxi-doroga-dobra.ru/blog/ | head -n1
```

## Серия «Примеры ситуаций» (из DeepSeek)

- Манифест: `scripts/assets/blog/situations/manifest.json` (без ПДн).
- Генерация HTML: `python scripts/generate_blog_situations.py`
- Сид WP: `bash scripts/wp_seed_blog_situations.sh`
- Рубрики: `/blog/rubrika/situacii/`, `/blog/rubrika/analitika/`
- Правило: **1 клиентский кейс → 1 статья-пример**; **каждые 5 → аналитика**.
- Не копировать `summary` из `knowledge/cases/*.json` в блог как есть (там draft и возможны остатки ПДн).
