# Яндекс Вебмастер — документация для разработчиков (оглавление)

Источники: [API Вебмастера](https://yandex.ru/dev/webmaster/doc/ru/) · срез: 2026-07-28  
Формат: **ссылка · раздел · кратко · для SFRFR**.

Base: `https://api.webmaster.yandex.net/` · Auth: OAuth Яндекс ID (`Authorization: OAuth …`).

## Статус SFRFR (исполнение)

| Тема | Статус | Где |
|------|--------|-----|
| Отдельный OAuth app | ✅ | `secrets/yandex-webmaster.env` |
| user / hosts / verification | ✅ | `scripts/yandex_webmaster_ensure_site.py` |
| sitemap user-added | ✅ | ensure |
| summary / indexing | ⏳ до load | ensure печатает статус |
| recrawl после сида | ✅ | `scripts/yandex_webmaster_recrawl.py` |
| CI-проверка «сайт в Вебмастере» | ✅ | ensure exit 0 + VERIFIED |

---

## API: старт и ресурсы

| Ссылка | Раздел | Кратко | Для SFRFR |
|--------|--------|--------|-----------|
| [Введение API](https://yandex.ru/dev/webmaster/doc/ru/) | Intro | REST JSON/XML, HTTPS | **P1** |
| [Обзор ресурсов](https://yandex.ru/dev/webmaster/doc/ru/concepts/getting-started) | Resources map | Таблица URI GET/POST/DELETE | **P0** |
| [User id](https://yandex.ru/dev/webmaster/doc/ru/reference/user) | `/user/` | Получить user-id | **P0** |
| [Список хостов](https://yandex.ru/dev/webmaster/doc/ru/reference/hosts) | `/hosts/` | Сайты аккаунта | **P0** |
| [Добавить сайт](https://yandex.ru/dev/webmaster/doc/ru/reference/hosts-add-site) | POST host | Программное добавление | P2 — UI достаточно |
| [Инфо о сайте](https://yandex.ru/dev/webmaster/doc/ru/reference/hosts) → host-id | Host details | Метаданные хоста | P1 |
| [Summary](https://yandex.ru/dev/webmaster/doc/ru/reference/host-id-summary) | Stats summary | Сводка по сайту | **P1** |
| [Verification](https://yandex.ru/dev/webmaster/doc/ru/reference/host-verification-get) | Verify | Статус подтверждения прав | **P0** |
| [Indexing history](https://yandex.ru/dev/webmaster/doc/ru/reference/hosts-indexing-history) | Index history | История индексации | **P1** |
| [Recrawl](https://yandex.ru/dev/webmaster/doc/ru/reference/host-recrawl-get) | Recrawl | Переобход URL | **P1** — после деплоя статей |
| [Старый dg hub](https://yandex.ru/dev/webmaster/doc/dg/) | Legacy path | Может редиректить | P2 |

---

## Auth для API

| Тема | Суть | Для SFRFR |
|------|------|-----------|
| OAuth app | Отдельное приложение на oauth.yandex.ru со scopes Вебмастера | **P1** |
| Header | `Authorization: OAuth <token>` | **P0** |
| Не смешивать | Токен Workspace ≠ обязательно токен Вебмастера (лучше разные apps) | **P0** |

См. папку `Yandex ID/`.

---

## Карта усиления SFRFR

| Цель | Читать |
|------|--------|
| Мониторинг индекса блога | summary · indexing-history |
| Пинг переобхода после `wp_seed` | recrawl |
| CI-проверка «сайт в Вебмастере» | user · hosts · verification |
| SEO ops без UI | getting-started map |

---

## Связь с ТЗ-10

- `sitemap.xml`, Search Console **и** Вебмастер — оба контура.  
- Канонический хост: `https://proverkastaza.ru` (алиасы только 301).
