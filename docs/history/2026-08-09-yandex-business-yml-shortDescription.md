# 2026-08-09 — прайс YML без shortDescription

## Запрос

Валидатор Вебмастера (схема «Маркет») отклонил публичный фид из‑за элемента `shortDescription`.

## Выполнено

- из `scripts/assets/yandex-business/price-list.yml` удалён недопустимый `shortDescription`;
- тексты тарифов оставлены в допустимом `description`;
- шаблон `price-list-template.xml` приведён к той же схеме;
- обновлена дата каталога;
- фид выкладывается на сайт через `wp_deploy_yandex_business_price.sh` при деплое VPS.

## Проверка

В XML-валидаторе: категория **Маркет**, ссылка
`https://proverkastaza.ru/yandex-business-price.yml`.
