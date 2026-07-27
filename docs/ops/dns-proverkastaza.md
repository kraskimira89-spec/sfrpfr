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

## Почта Яндекс 360 (MX + DKIM)

Официальные инструкции: [MX](https://yandex.ru/support/yandex-360/business/admin/ru/domains/dns/mx.html) · [DKIM](https://yandex.ru/support/yandex-360/business/admin/ru/domains/dns/dkim.html).

DNS у **reg.ru** (`ns1.reg.ru` / `ns2.reg.ru`).

### MX (сделано, если nslookup показывает mx.yandex.net)

| Тип | Subdomain / хост | Mail Server / значение | Priority |
|-----|------------------|------------------------|----------|
| MX | `@` | `mx.yandex.net.` (точка в конце) | `10` |

### SPF (TXT на `@`)

| Тип | Хост | Значение |
|-----|------|----------|
| TXT | `@` | `v=spf1 redirect=_spf.yandex.net` |

### DKIM (нужно сейчас — «письма попадут в спам»)

1. В [admin.yandex.ru/domains](https://admin.yandex.ru/domains) → **Настроить DKIM** → скопировать **публичный ключ** (строка `v=DKIM1; k=rsa; … p=…`).
2. В reg.ru → DNS-зона `proverkastaza.ru` → добавить **TXT**:

| Тип | Subdomain / хост | Text / значение |
|-----|------------------|-----------------|
| TXT | `mail._domainkey` | *вставить ключ целиком из кабинета Яндекса* |

3. Подождать 5–30 мин → в кабинете **Проверить**.
4. **Не трогать** A-записи сайта (`@` / `www` / `api` … → `91.229.11.147`).

Проверка MX:

```powershell
nslookup -type=MX proverkastaza.ru 8.8.8.8
```

Проверка DKIM:

```powershell
nslookup -type=TXT mail._domainkey.proverkastaza.ru 8.8.8.8
```

После зелёного статуса DNS: сотрудник `info@proverkastaza.ru` (или аналог) → OAuth Телемост этим ящиком.

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
