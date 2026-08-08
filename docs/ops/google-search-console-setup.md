# Google Search Console — proverkastaza.ru

**SA:** `sfrpfr-google-search-console@sfrfr-sheets.iam.gserviceaccount.com`  
**Ключ:** `secrets/sfrfr-sheets-Google-Search-Console-06b255b04ddd.json`

## Статус API (2026-08-08)

| Шаг | Статус |
|-----|--------|
| Ключ SA / `gsc-sites` | ✅ работает, property пока **0** |
| Site Verification API | ❌ выключен в GCP `sfrfr-sheets` — нужен клик владельца |
| DNS TXT через reg.ru | ❌ нет `secrets/regru.env` |
| META в WP | ✅ MU `sfrfr-google-verification.php` (токен из config) |

## Разово включить API (владелец Google Cloud)

Открыть и нажать **Enable**:

https://console.developers.google.com/apis/api/siteverification.googleapis.com/overview?project=sfrfr-sheets

## Автоподтверждение Domain (DNS) — после Enable + regru.env

```powershell
# secrets/regru.env — см. docs/ops/regru.env.example
$env:PYTHONPATH="src"
python scripts/google_search_console_verify_domain.py --method dns
```

Скрипт: получит TXT → добавит в reg.ru → verify → добавит `sc-domain:proverkastaza.ru` в GSC.

## Автоподтверждение URL-prefix (META)

```powershell
$env:PYTHONPATH="src"
python scripts/google_search_console_verify_domain.py --method meta
# затем на VPS:
# cp scripts/wp-mu-plugins/sfrfr-google-verification* /var/www/.../mu-plugins/
# wp cache flush
# снова verify (скрипт уже вызывает verify)
```

## Ручной путь (как на скрине гайда)

1. [Search Console](https://search.google.com/search-console) → Добавить ресурс → **Домен** → `proverkastaza.ru`
2. Скопировать TXT → reg.ru DNS → `@` TXT
3. Подтвердить
4. Настройки ресурса → Пользователи → добавить SA  
   `sfrpfr-google-search-console@sfrfr-sheets.iam.gserviceaccount.com` с правами **Владелец**
5. Проверка: `PYTHONPATH=src python -m sfrfr gsc-sites`
