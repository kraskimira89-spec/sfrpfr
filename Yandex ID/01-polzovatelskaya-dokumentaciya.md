# Яндекс ID — пользовательская документация (оглавление)

Источники: [Help ID](https://yandex.ru/support/id/) · [oauth.yandex.ru](https://oauth.yandex.ru/) · срез: 2026-07-28  
Формат: **ссылка · раздел · кратко · для SFRFR**.

Рабочий ящик: `proverkastaza@yandex.ru` · гайд: `docs/ops/yandex-workspace-setup.md` · ТЗ-14.

> **Не путать:** Яндекс ID / OAuth (почта, Телемост, API сервисов) ≠ Yandex Cloud API-ключ / AI Studio.

---

## Как пользоваться

| Приоритет | Смысл |
|-----------|--------|
| **P0** | OAuth-приложение, токен, scopes для Workspace |
| **P1** | Безопасность аккаунта, отзыв доступа |
| **P2** | LoginSDK / «войти через Яндекс» на витрине (не MVP) |

---

## Аккаунт и помощь пользователю

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [Яндекс ID — помощь](https://yandex.ru/support/id/index.html) | Help hub | Управление аккаунтом Яндекса | **P0** — служебный ящик |
| [Passport help](https://yandex.ru/support/passport/) | Паспорт | Старые/смежные статьи входа | P1 |
| [id.yandex.ru](https://id.yandex.ru/) | Личный кабинет ID | Профиль, устройства, безопасность | **P0** |
| [oauth.yandex.ru](https://oauth.yandex.ru/) | Консоль приложений | Создать/отозвать OAuth-клиент | **P0** |

---

## Регистрация приложений (админ)

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [О сервисе API ID](https://yandex.ru/dev/id/doc/ru/) | Dev intro | Зачем OAuth Яндекса | **P0** |
| [Регистрация для API](https://yandex.ru/dev/id/doc/ru/register-api) | register-api | Приложение «для доступа к API» | **P0** — Workspace |
| [Регистрация клиента](https://yandex.ru/dev/id/doc/ru/register-client) | register-client | Классическая регистрация OAuth-клиента | **P0** |
| [Подтверждение через Госуслуги](https://yandex.ru/dev/id/doc/ru/confirm-account) | Trust | Повысить доверие к приложению | P2 |

---

## Быстрый указатель

| Задача | Смотреть |
|--------|----------|
| Создать SFRFR Workspace app | register-api · oauth.yandex.ru · yandex-workspace-setup.md |
| Отозвать скомпрометированный токен | oauth.yandex.ru · id.yandex.ru |
| Не смешать с Cloud AI | ТЗ-14 vs `YANDEX_API_KEY` |
