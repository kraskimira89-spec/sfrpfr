# 2026-08-23 — Mobile drawer: BVI и toggle подменю

## Проблема

В открытом бургер-меню (≤921px):

- плавающий BVI (`sfrfr-edge-floats`, z-index 100050) перекрывал правый край drawer и `.ast-menu-toggle`;
- у пунктов с подменю дублировались стрелки (в `.menu-link` и в `button.ast-menu-toggle`), зоны тапа сливались.

## Фикс

`sfrfr-landing.css` — блок **sfrfr-mobile-nav-v3** в `@media (max-width: 921px)`:

- `body.ast-main-header-nav-open` / `ast-popup-nav-open` — скрыть `.sfrfr-edge-floats`;
- `.menu-item-has-children` — flex-row: ссылка слева, toggle 44×44 справа (`margin-left: auto`);
- inline `.dropdown-menu-toggle` в ссылке скрыт на mobile;
- `.sub-menu` — full width под родителем, indent, фон-подложка;
- min-height 44px для touch targets.

Проверка: `/` mobile — «Главная» / «Услуги» раскрываются по стрелке справа, BVI не перехватывает тап.
