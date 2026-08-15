# Стратегия размещения бренд-визуалов на сайте

**Статус:** рабочая схема (после пакета assets 2026-08-10)  
**Канон:** [brand-platform-v2.md](brand-platform-v2.md) · ТЗ: [spec-brand-rollout.md](spec-brand-rollout.md) §P2  
**Исходники:** `docs/brand/assets/` → на VPS копировать в `/wp-content/uploads/sfrfr/brand/`

---

## Принципы

1. **Один главный символ на экран** — не галерея из всех ассетов подряд.
2. **Не ломать сетку** — только существующие слоты (`.sfrfr-illustration`, lead-зона trust-страниц, карточки тарифов). Без новых секций «миссия/галерея».
3. **Подпись снаружи картинки** — кириллицу на PNG не печь; текст рядом классом `.sfrfr-muted` / note.
4. **Сначала утверждение** — в `docs/brand/assets/` статус «на согласовании»; на сайт только после OK по кадру.
5. **Форматы:** 16:9 — hero/обложки; 1:1 — карточки, посты, квадратные слоты.

---

## Куда какой файл

| Поверхность | Ассет | Как вшить |
|-------------|-------|-----------|
| Главная `/` | `viz-family-digital-support-16x9.png` | `.sfrfr-hero__grid` + `.sfrfr-illustration` |
| `/proverka-stazha/` | `viz-diagnostika-16x9.png` | то же |
| `/proverka-stazha-pered-pensiey/` | `viz-pered-pensiey-16x9.png` | то же |
| `/proverka-severnogo-stazha/` | `viz-severnyy-stazh-16x9.png` | то же |
| `/pomoch-rodstvenniku-proverit-stazh/` | `viz-family-digital-support-16x9.png` | то же |
| `/tarify/` | `viz-tarify-16x9.png` | то же; карточки тарифов ниже |
| `/kak-rabotaem/` | `viz-soprovozhdenie-16x9.png` | то же; шаги ниже |
| `/stazh-do-2002/` | `viz-stazh-do-2002-16x9.png` | то же |
| `/kontakty/` | `viz-kontakty-16x9.png` | то же |
| `/otzyvy/` | `viz-otzyvy-16x9.png` | lead + слот над карточками |
| `/expert/` | `viz-eksperty-16x9.png` | то же; фото экспертов ниже |
| Кабинет | `viz-kabinet-16x9.png` | запас |
| OG / посты | 1:1 | SEO / соцсети |

---

## Этапы внедрения

### Сейчас
- Family 16:9 **утверждён** и в hero главной (P2).
- Severnyy 16:9 **утверждён** на `/proverka-severnogo-stazha/`.
- Остальные ассеты в `docs/brand/assets/` — на согласовании.
- Deploy копирует `viz-*.png` в `wp-content/uploads/sfrfr/brand/`.

### Шаг A — P2 главная ✅
1. Скопировать PNG в `wp-content/uploads/sfrfr/brand/`.
2. В `sfrfr-home.html` заменить содержимое `.sfrfr-illustration` на `<img …>`.
3. Микроправка CSS только если пропорции рвут слот (scoped).
4. Сид home через существующий `wp_apply_home.php` / deploy.

### Шаг B — сегментные страницы
- Север ✅: один кадр на `/proverka-severnogo-stazha/` (вышка слева / факел справа).
- Родственники: family, если нужен визуальный якорь.
- Не вешать все три тарифа картинками на главную — шум.

### Шаг C — вне сайта
- Яндекс Бизнес посты, MAX-канал, превью статей — 1:1 из того же набора.
- Не дублировать разные стили «на глаз».

---

## Чего не делать

- Full-bleed фото-баннер поверх всей главной с ломкой hero grid.
- Слайдер всех viz-* на первом экране.
- Имитация Госуслуг / герб / триколор поверх ассетов.
- Массовая переклейка блога пакетом (blog-manual-only).

---

## Критерий «картинка на месте»

Редакторский тест v2: уважение к человеку + понятный следующий шаг?  
За 3 секунды читается партнёрство / сверка / северный труд — не опека и не обещание выплат.
