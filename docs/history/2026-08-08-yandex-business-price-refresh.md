# 2026-08-08 — Обновление прайса Яндекс Бизнеса

## Зачем
В кабинете Sprav `82469923047` раздел «Товары и услуги» пустой — нужна загрузка XLS/YML.

## Что сделано
- Обновлены `price-list.yml` и `price-list.xlsx`: 3 тарифа с сайта (3000 / 10000 / 25000).
- YML: `vendor`, `currencyId=RUB`, `description` (без `shortDescription` — схема Маркета), актуальная дата.
- XLSX: «Популярный товар» = «Да», «В наличии» пусто (публиковать).
- Публичный фид: `https://proverkastaza.ru/yandex-business-price.yml`.
- В ops обновлён ID кабинета на `82469923047`.

## Как загрузить
О компании → Товары и услуги → Загрузить XLS/YML → `scripts/assets/yandex-business/price-list.xlsx`.
