# Яндекс ID — документация для разработчиков (оглавление)

Источники: [API Яндекс ID](https://yandex.ru/dev/id/doc/ru/) · срез: 2026-07-28  
Формат: **ссылка · раздел · кратко · для SFRFR**.

Код (план): `src/sfrfr/integrations/yandex_workspace/` · env `YANDEX_OAUTH_*` · **не** `YANDEX_API_KEY`.

---

## OAuth и токены

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [OAuth в Яндексе](https://yandex.ru/dev/id/doc/ru/concepts/ya-oauth-intro) | Протокол | Roles, code/token, особенности Яндекса | **P0** |
| [Подключение к API](https://yandex.ru/dev/id/doc/ru/how-to) | How-to | Шаги интеграции Login / токен | **P0** |
| [Получение доступа / токена](https://yandex.ru/dev/id/doc/ru/access) | Access | Authorization code / token flow | **P0** |
| [Code in URL](https://yandex.ru/dev/id/doc/ru/codes/code-url) | Auth code | Код в redirect | **P0** — callback API |
| [Refresh token](https://yandex.ru/dev/id/doc/ru/tokens/refresh-client) | Refresh | Обновление access token | **P0** — долгий серверный доступ |
| [Debug token](https://yandex.ru/dev/id/doc/ru/tokens/debug-token) | Debug | Проверка токена | **P1** |
| [Данные пользователя](https://yandex.ru/dev/id/doc/ru/user-information) | Userinfo | login, email, phone, avatar | P1 — только если Login на сайт |
| [Мгновенная авторизация](https://yandex.ru/dev/id/doc/ru/suggest-description) | Suggest / one-tap | Виджет входа на сайт | P2 — кабинет у нас через MAX/Supabase |
| [LoginSDK mobile](https://yandex.ru/dev/id/doc/ru/mobileauthsdk/about) | Mobile SDK | iOS/Android | P2 |
| [Условия API](https://yandex.ru/legal/authid_api/) | Legal | ToS API ID | P1 |

---

## Связь с другими API Яндекса

OAuth-токен Яндекс ID используется как `Authorization: OAuth …` для:

| Сервис | Зачем SFRFR | Где доки |
|--------|-------------|----------|
| Почта / Календарь / Диск / Телемост | ТЗ-14 Workspace | ТЗ-14 + ops setup |
| Метрика API | Отчёты/цели программно | папка `Yandex Metrika/` |
| Вебмастер API | Индексация/запросы | папка `Yandex Webmaster/` |

Scopes выбирать в UI oauth.yandex.ru под каждое приложение (лучше **отдельные** apps: Workspace / Metrika / Webmaster).

---

## Карта усиления SFRFR

| Цель | Читать |
|------|--------|
| Server OAuth для `proverkastaza@…` | register-api · access · refresh-client |
| Callback `api.proverkastaza.ru/.../oauth/callback` | codes/code-url · how-to |
| Login «Войти через Яндекс» в cabinet | suggest + user-information — **не приоритет** (MAX/Supabase) |
| Ротация при утечке | oauth revoke · новый token · debug-token |

---

## Уже в проекте

| Тема | Где |
|------|-----|
| ТЗ Workspace | `docs/specs/14-yandex-workspace.md` |
| Клики в UI | `docs/ops/yandex-workspace-setup.md` |
| Secrets | `secrets/yandex-workspace.env` |
