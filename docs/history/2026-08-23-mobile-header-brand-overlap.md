# 2026-08-23 — Mobile: бренд перекрывал бургер

## Проблема

На mobile бургер ☰ был перекрыт хвостом текста «Проверка стаж**а**» (видны буквы «ЖА»).

## Причина

`sfrfr-header-layout-v1` задавал `min-width: max-content` и `flex-shrink: 0` для `.site-header .site-branding` и `[data-section="title_tagline"]` **без media query** — правила действовали и на `#ast-mobile-header`. Mobile-блок `sfrfr-mobile-nav-v1` не переопределял обёртку `title_tagline`, ellipsis не срабатывал.

## Фикс

- `sfrfr-header-layout-v1` — только `@media (min-width: 922px)` (desktop).
- `sfrfr-mobile-nav-v2` — flex-row в `#ast-mobile-header`: logo | title (ellipsis) | burger 44×44px; `min-width: 0` на всей цепочке flex-родителей.

Проверка: `/`, `/kontakty/`, `/proverka-stazha/` — бургер кликабелен, drawer открывается.
