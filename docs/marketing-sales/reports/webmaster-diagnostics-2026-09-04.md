# Диагностика Яндекс Вебмастера (2026-09-04)

Снято: `2026-09-04T14:20:21+03:00` · скрипт `scripts/yandex_webmaster_diagnostics.py`

**Канон:** смотреть только apex `https://proverkastaza.ru` (без www).
Зеркала `www` / `http` с 301 — предупреждения там ожидаемы.

UI: [диагностика apex](https://webmaster.yandex.ru/site/https%3Aproverkastaza.ru%3A443/diagnostics/)

## Apex (действия)

- searchable_pages: **7**
- excluded_pages: 0
- site_problems: `{}`

✅ Активных проблем на apex **нет**.

## Все хосты (справка)

### http://proverkastaza.ru
- diagnostics: OK

### https://proverkastaza.ru
- diagnostics: OK

### https://www.proverkastaza.ru
- diagnostics: OK

### http://www.proverkastaza.ru
- `MAIN_MIRROR_IS_NOT_HTTPS` (POSSIBLE_PROBLEM) _(зеркало, можно игнорировать)_
- `NOT_IN_SPRAV` (RECOMMENDATION) _(зеркало, можно игнорировать)_
- `NO_REGIONS` (RECOMMENDATION) _(зеркало, можно игнорировать)_

## Автоисправления

- OK ensure_site
- after_probe: OK

## Как обновить

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/yandex_webmaster_diagnostics.py --report --fix --ssh
```
