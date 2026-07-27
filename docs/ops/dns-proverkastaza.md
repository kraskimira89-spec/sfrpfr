# DNS: переход на proverkastaza.ru (reg.ru)

IP VPS: **`91.229.11.147`**  
NS: `ns1.reg.ru` / `ns2.reg.ru` (как у старого домена).

## Основной домен `proverkastaza.ru`

| Тип | Имя (хост) | Значение |
|-----|------------|----------|
| A | `@` | `91.229.11.147` |
| A | `www` | `91.229.11.147` |
| A | `api` | `91.229.11.147` |
| A | `cabinet` | `91.229.11.147` |
| A | `admin` | `91.229.11.147` |

## Почта Яндекс 360 (MX)

Официальная инструкция: [MX-запись Яндекс 360](https://yandex.ru/support/yandex-360/business/admin/ru/domains/dns/mx.html).

DNS у **reg.ru** (`ns1.reg.ru` / `ns2.reg.ru`). Сейчас MX для `proverkastaza.ru` **нет** — почта на домене не заработает, пока не добавите.

### В панели reg.ru

1. [reg.ru](https://www.reg.ru) → домен `proverkastaza.ru` → **DNS-серверы и управление зоной**.
2. **Удалите** все существующие MX (если появятся).
3. **Добавьте** MX:

| Тип | Subdomain / хост | Mail Server / значение | Priority |
|-----|------------------|------------------------|----------|
| MX | `@` | `mx.yandex.net.` (точка в конце) | `10` |

4. Рекомендуется сразу SPF (TXT), чтобы письма не уходили в спам:

| Тип | Хост | Значение |
|-----|------|----------|
| TXT | `@` | `v=spf1 redirect=_spf.yandex.net` |

(Точное значение SPF также смотрите в подсказках admin.yandex.ru для вашего домена — иногда Яндекс показывает готовый TXT.)

5. **Не трогайте** A-записи `@` / `www` / `api` / `cabinet` / `admin` → `91.229.11.147`.

6. Подождите распространения DNS (минуты–часы, редко до 72 ч). В [admin.yandex.ru/domains](https://admin.yandex.ru/domains) → домен → **Проверить**.

Проверка:

```powershell
nslookup -type=MX proverkastaza.ru 8.8.8.8
```

Ожидается: `proverkastaza.ru MX preference = 10, mail exchanger = mx.yandex.net`.

После MX: создайте сотрудника `info@proverkastaza.ru` (или аналог) и этим ящиком выпускайте OAuth для Телемост API.

## Защитные домены (только редирект)

### `proverka-staza.ru`

| Тип | Имя | Значение |
|-----|-----|----------|
| A | `@` | `91.229.11.147` |
| A | `www` | `91.229.11.147` |

### `prostaz.ru`

| Тип | Имя | Значение |
|-----|-----|----------|
| A | `@` | `91.229.11.147` |
| A | `www` | `91.229.11.147` |

## Старый `taxi-doroga-dobra.ru`

Оставить A `@` / `www` / `api` / `cabinet` / `admin` на тот же IP — после cutover Apache отдаёт **301** на `proverkastaza.ru` (и поддомены API/кабинетов на новые имена).

## После DNS

Проверка с ПК:

```powershell
nslookup proverkastaza.ru
nslookup api.proverkastaza.ru
```

Должен быть `91.229.11.147`. Затем на VPS:

```bash
sudo bash /opt/sfrfr/scripts/vps_cutover_proverkastaza.sh
```

Или с ПК (если код ещё не на VPS): после `git push` дождаться deploy и выполнить скрипт по SSH.

## Ручные шаги после cutover

1. **MAX** → Чат-боты → «Стаж и пенсия» → URL мини-приложения: `https://proverkastaza.ru/app/`
2. **Supabase Auth** → Site URL / Redirect URLs: `https://cabinet.proverkastaza.ru/**` (см. `docs/ops/supabase-auth-redirects.md`)
3. Webhook: `sfrfr max-subscribe` (если `PUBLIC_BASE_URL` сменился)
