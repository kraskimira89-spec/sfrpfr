# Сравнение доступа к сайту — 2026-10-27

**URL канон:** `https://proverkastaza.ru/`  
**Метод:** `GET` (дополнительно `HEAD`)  
**Дата (UTC):** 2026-10-27  
**Исход прогона:** машина в РФ (`country_iso=RU` по ifconfig.co)

## Конфиг сервера (репозиторий)

В `infra/apache/geo-russia-only.conf` доступ к `/` разрешён только при:

- localhost, или
- `GEO_ALLOW` (краулеры / `sfrfr-*` UA из `geo-allow-bots.conf`), или
- GeoIP `MM_COUNTRY_CODE == 'RU'`.

Заголовок ответа: `X-Geo-Policy: RU-only+bots`.

Это **описание политики**, не замена живой проверки из-за рубежа.

## Живые запросы (один URL, GET)

| Клиент | Follow redirects | Status | Location | Server | X-Geo-Policy | Content-Type |
|---|---|---|---|---|---|---|
| Chrome UA (Win) | no | 200 | — | Apache | RU-only+bots | text/html; charset=UTF-8 |
| Chrome UA | yes | 200 | — | Apache | RU-only+bots | text/html; charset=UTF-8 |
| curl default UA | no | 200 | — | Apache | RU-only+bots | text/html; charset=UTF-8 |
| curl default | yes | 200 | — | Apache | RU-only+bots | text/html; charset=UTF-8 |
| Googlebot UA | no | 200 | — | Apache | RU-only+bots | text/html; charset=UTF-8 |
| Googlebot UA | yes | 200 | — | Apache | RU-only+bots | text/html; charset=UTF-8 |
| HEAD (Chrome) | no | 200 | — | Apache | (как выше) | text/html; charset=UTF-8 |

DNS A: `proverkastaza.ru` → `91.229.11.147`.

### Редиректы смежных URL (тот же метод GET)

| URL | Status | Location |
|---|---|---|
| `http://proverkastaza.ru/` | 301 | `https://proverkastaza.ru/` |
| `https://www.proverkastaza.ru/` | 301 | `https://proverkastaza.ru/` |

На 301 также виден `X-Geo-Policy: RU-only+bots`.

## Браузер vs автозапрос

| Канал | Результат |
|---|---|
| Автоматический curl с RU egress | **200** (таблица выше) |
| Браузер (IDE browser → сайт) | см. снимок в отчёте UI / отдельный шаг |
| Зарубежный прокси | **проверка не состоялась** (таймаут) — **не** доказательство блокировки |
| Зарубежный 403 из прошлых материалов | **не перепроверен** в этой сессии |

## Вывод (ограниченный)

1. Из РФ при одинаковом URL/методе ответ **стабильно 200** для обычного UA, curl и Googlebot UA; цепочка редиректов `http`/`www` → apex штатная.
2. Сервер **объявляет** политику `RU-only+bots` заголовком и конфигом Apache — это объясняет, почему **в принципе** доступ может различаться для не-RU без bot-UA, но:
3. **В этой сессии** зарубежный 403 **не воспроизведён**; таймаут прокси = «проверка не состоялась».
4. Поэтому нельзя на основании только этого прогона утверждать «зарубежье всегда 403» или списывать прошлый 403 исключительно на UA без повторной проверки с известным не-RU egress.

## Не доказано этим отчётом

- Живой 403 с не-RU IP.
- Что отличие вызвано только географией или только User-Agent (нужен контролируемый не-RU egress).
