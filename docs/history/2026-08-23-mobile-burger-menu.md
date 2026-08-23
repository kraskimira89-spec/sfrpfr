# 2026-08-23 — Mobile: бургер-меню

## Проблема

На mobile в бургере не было главного меню (Главная / Услуги / Контакты…):
- Astra `mobile_menu` не был привязан к SFRFR Primary — показывался fallback «все страницы»;
- CSS desktop-dropdown (`position: absolute` + `display:flex` на `.main-header-menu`) ломал drawer.

## Фикс

- `sfrfr-nav-mobile.php` — mobile drawer использует то же меню, что `primary`.
- `sfrfr-landing.css` — `sfrfr-mobile-nav-v1`: z-index 1100, бургер не уезжает, submenu static в drawer; dropdown-стили только `@media (min-width: 922px)`.
- `wp_seed_site_tz02.sh` — assign `mobile_menu`.

Проверка mobile: `/`, `/kontakty/`, `/proverka-stazha/` — бургер справа, по тапу пункты как в desktop.
