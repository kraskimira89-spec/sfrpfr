# Playbook: посадочная `/partneram/`

Операционная памятка по странице для общественных приёмных, НКО и социальных партнёров.

## URL

| URL | Назначение |
|-----|------------|
| https://proverkastaza.ru/partneram/ | Каноническая посадочная |
| https://proverkastaza.ru/prezentaciya-dlya-deputata/ | 301 → `/partneram/` |

Страница **открытая**: `index, follow`, есть в `wp-sitemap-pages-*.xml`.

## Где ссылка на сайте

- Шапка: пункт меню **«Партнёрам»** (`SFRFR Primary`)
- Футер: колонка «Документы» → **Партнёрам**

## Редактирование контента

1. HTML-ассет: `scripts/assets/trust/partneram.html`
2. Сид: `scripts/wp_seed_trust_pages_tz18.php` (slug `partneram`)
3. Стили (только scoped): конец `scripts/assets/sfrfr-landing.css` (`#sfrfr-partneram-page`)
4. После правок: commit → `deploy-vps` → на VPS:
   ```bash
   bash /opt/sfrfr/scripts/wp_seed_trust_pages_tz18.sh
   bash /opt/sfrfr/scripts/wp_apply_landing_vps.sh
   ```

## Презентация PPTX

- Metabox в админке WP на странице «Партнёрам»: **Презентация для партнёров (PPTX)**
- Meta: `_sfrfr_presentation_file` (ID вложения)
- При первом сиде файл берётся из `docs/proverkastaza_presentation_for_deputy.pptx`, если meta ещё пустая
- Если файла нет: на странице текст «Презентация предоставляется по запросу», кнопка скрыта
- CTA подставляется MU `scripts/wp-mu-plugins/sfrfr-partneram.php` по маркеру `<!-- SFRFR_PRESENTATION_CTA -->`

## SEO

- Title: «Партнёрам: проверка стажа, ИЛС и подготовка обращения в СФР»
- Description: в сиде `wp_seed_trust_pages_tz18.php`
- Map title: `scripts/wp-mu-plugins/sfrfr-seo-meta.php` (slug `partneram`)

## Юридические рамки (не менять без согласования)

- Не агитация, не партийная символика, не обещания перерасчёта
- Нет форм сбора ПДн на странице
- Канон подачи: `scripts/assets/copy/submission-position.md`

## Rollback

1. Удалить пункт «Партнёрам» из меню и футера (revert MU footer + menu seed)
2. `wp post delete $(wp post list --name=partneram --field=ID) --force`
3. Revert HTML/CSS/MU/redirect
4. `wp cache flush`

PPTX в Media Library можно оставить.

## Связанные файлы

- `scripts/assets/trust/partneram.html`
- `scripts/wp-mu-plugins/sfrfr-partneram.php`
- `scripts/wp-mu-plugins/sfrfr-seo-redirects.php` (301)
- `docs/ops/seo-url-decision-map.md`
