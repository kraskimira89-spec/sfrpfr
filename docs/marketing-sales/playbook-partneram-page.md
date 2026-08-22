# Playbook: посадочная `/partneram/`

Операционная памятка по странице для общественных приёмных, НКО и социальных партнёров.

## URL

| URL | Назначение |
|-----|------------|
| https://proverkastaza.ru/partneram/ | Каноническая посадочная |
| https://proverkastaza.ru/prezentaciya-dlya-deputata/ | 301 → `/partneram/` |

Страница **открытая**: `index, follow`, есть в `wp-sitemap-posts-page-*.xml`.

## Где ссылка на сайте

- Шапка: пункт меню **«Партнёрам»** (`SFRFR Primary`) — **перед «Контакты»**
- Футер: колонка «Документы» → **Партнёрам**

Пересборка меню на VPS (только структура WP-меню):

```bash
SFRFR_REBUILD_MENU=1 bash /opt/sfrfr/scripts/wp_apply_landing_vps.sh
```

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
- CTA «Скачать презентацию» — MU `sfrfr-partneram.php` по маркеру `<!-- SFRFR_PRESENTATION_CTA -->`

## B2B-форма «Партнёрство»

- Скрипт: `scripts/wp_ensure_partner_form.php` (WPForms, subject `partnerstvo`, email `info@proverkastaza.ru`)
- **Не** уходит в FastAPI/amoCRM (только email-уведомление)
- Поля: организация, ФИО и должность, рабочий телефон, почта, регион, формат взаимодействия, согласие ПДн
- **Без** СНИЛС, паспортов, загрузки документов граждан
- На странице: маркер `<!-- SFRFR_PARTNER_FORM -->` → MU подставляет shortcode
- SmartCaptcha: `sfrfr-recaptcha-lead.php` на `/partneram/` (как на главной)

## SEO

- Title: «Партнёрам — навигация по пенсионным документам | Проверка стажа»
- Description: «Партнёрский формат информационно-документарной помощи: выписка ИЛС, пенсионный стаж, трудовые документы, подготовка обращений в СФР.»
- H1: «Партнёрам: понятная навигация по пенсионным документам»
- Map title: `scripts/wp-mu-plugins/sfrfr-seo-meta.php` (slug `partneram`)

## CTA

| Кнопка | Назначение |
|--------|------------|
| Скачать презентацию | PPTX из Media Library |
| Обсудить партнёрский формат | Якорь `#partnerstvo` → B2B-форма |

## Метрика (цели)

| Цель | Событие |
|------|---------|
| `partner_page_view` | Просмотр `/partneram/` |
| `partner_pptx_download` | Клик «Скачать презентацию» |
| `partner_cta_click` | Клик «Обсудить партнёрский формат» |
| `partner_lead_ok` | Успешная B2B-заявка |

## Юридические рамки (не менять без согласования)

- Не агитация, не партийная символика, не обещания перерасчёта
- B2B-форма — только для организаций; не собирать документы граждан
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
- `scripts/wp_ensure_partner_form.php`
- `scripts/wp-mu-plugins/sfrfr-seo-redirects.php` (301)
- `docs/ops/seo-url-decision-map.md`
