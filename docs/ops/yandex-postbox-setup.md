# Yandex Cloud Postbox — исходящая почта + delivery webhooks

**Дата:** 2026-09-02  
**Тикет:** [SFRFR-40](https://tracker.yandex.ru/SFRFR-40)  
**Связано:** ТЗ-31, `secrets/yandex-postbox.env` (не в git)

## Статус (2026-09-02)

| Шаг | Статус |
|-----|--------|
| SA `sfrfr-postbox` + роли `postbox.admin/sender/viewer` | ✅ |
| Static access key на VPS | ✅ (`YANDEX_POSTBOX_*`) |
| Domain identity `proverkastaza.ru` (BYODKIM) | ✅ ждёт DNS |
| Configuration set `sfrfr-default` | ✅ |
| Cloud Function `sfrfr-postbox-webhook` | ✅ (нужен YDS trigger) |
| `YANDEX_POSTBOX_ENABLED` | ❌ `false` до Success DKIM |
| DNS SPF + DKIM TXT на reg.ru | ✅ |
| Postbox Verification / DKIM SUCCESS | ✅ 2026-09-02 |
| `YANDEX_POSTBOX_ENABLED` | ✅ `true` |
| Data Streams + event destination + trigger | ⏳ |

---

## 1. DNS в reg.ru (сейчас)

NS: `ns1.reg.ru` / `ns2.reg.ru`. Панель: DNS-зона `proverkastaza.ru`.

### 1.1 SPF (заменить существующую TXT)

Сейчас: `v=spf1 redirect=_spf.yandex.net`  

`redirect` **нельзя** комбинировать с Postbox. Замени **ту же** TXT на `@` на:

```text
v=spf1 include:_spf.yandex.net include:spf.postbox.yandexcloud.net ~all
```

Яндекс 360 (MX) и Postbox остаются в одной SPF. Вторую SPF-запись не создавать.

### 1.2 DKIM (новая TXT)

| Тип | Хост (subdomain) | Значение |
|-----|------------------|----------|
| TXT | `sfrfrpostbox._domainkey` | **полная** строка ниже |

⚠️ **Важно:** в DNS должно быть именно `v=DKIM1; k=rsa; p=…` целиком.  
Если записано только `p=…` — Postbox даёт `DkimStatus=FAILED` / `VerificationStatus=FAILED` (проверено 2026-09-02).

Значение (одна строка; в reg.ru можно в кавычках):

```text
v=DKIM1; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA9gjJllds5GAd/Uq4bHg/r83aE9CVQsdUDxYYfaiOveOj3iwnui/bpzrsQ/YWXQjA8M8U/CQn/Vgf1u2VlcTIWq4N4Y8DQ+rUv/vmRWDJS2AWc3eaF1Lu+WlN4RgNMPrwt48LU+yOFDBLegHvSMsWbZizPGfzJOUgaXOwsiPWSHnrJg5yh2tj1q7H4/l0AJEfm83q8cN9HtMLa/WMZ1wI90wDOTk6fF3Zb3qB7S3ZK6T9vcY1tlTzKHB9WEj8pFqZeyDe3lZcmY6VWsHigmjJhaP3dRhphBt9rlevuXjDo1jO9/LolqQc669aSLLDsKw7P7mpofMmFFAf5oENaZgZEwIDAQAB
```

Копия: `secrets/postbox-dkim-dns.txt`.

Проверка:

```powershell
Resolve-DnsName sfrfrpostbox._domainkey.proverkastaza.ru -Type TXT -Server 8.8.8.8 |
  ForEach-Object { $_.Strings -join '' }
```

Ожидание: строка **начинается** с `v=DKIM1; k=rsa; p=`.

Не трогать: `mail._domainkey` (Яндекс 360), A-записи сайта.

### 1.3 DMARC (опционально)

| Тип | Хост | Значение |
|-----|------|----------|
| TXT | `_dmarc` | `v=DMARC1; p=none` |

### 1.4 Проверка

```powershell
nslookup -type=TXT sfrfrpostbox._domainkey.proverkastaza.ru 8.8.8.8
nslookup -type=TXT proverkastaza.ru 8.8.8.8
```

В консоли YC → Postbox → адрес `proverkastaza.ru` → **Запустить проверку**, дождаться `SUCCESS` / `VerifiedForSendingStatus=true`.

После Success — напиши агенту: включим `YANDEX_POSTBOX_ENABLED=true` на VPS.

---

## 2. Уже сделано в YC / VPS

- Folder `b1g0mhpm9tr4lrurk1bu`, SA `sfrfr-postbox` (`ajeg79ih39jvnsvcnins`)
- Identity BYODKIM selector `sfrfrpostbox`
- Config set `sfrfr-default`
- CF `sfrfr-postbox-webhook` (`d4ebvqmdt4dr42l0p8oi`) → `POST …/api/webhooks/email/postbox`
- Env на VPS: ключи send + webhook Basic (см. `secrets/yandex-postbox.env`)

Redeploy CF: `.\scripts\yc_cloud_auth.ps1` затем `.\scripts\yc_postbox_deploy_cf.ps1`

---

## 3. Data Streams + trigger (после DNS)

1. **YDB / Data Streams**: поток `sfrfr-postbox-events` в том же folder.  
2. Postbox → configuration set `sfrfr-default` → event destination → этот поток  
   (типы: Send, Delivery, Bounce, Complaint, DeliveryDelay, …).  
3. Триггер CF на поток (Data Streams → `sfrfr-postbox-webhook`).  
4. Гайд: [postbox-webhook](https://yandex.cloud/ru/docs/postbox/tutorials/postbox-webhook).

Пока триггера нет — smoke вручную:

```text
POST /api/webhooks/email/postbox  (Basic из secrets)
```

---

## 4. Включение отправки

Когда DKIM = SUCCESS:

```text
YANDEX_POSTBOX_ENABLED=true
```

в `/opt/sfrfr/.env` + `systemctl restart sfrfr-api`.  
Health → `yandex_postbox_send: true`.  
`send_mail()` пойдёт в Postbox (`provider=yandex_postbox`).

Тест: симулятор доставки Postbox или письмо на свой ящик.

## Rollback

`YANDEX_POSTBOX_ENABLED=false` → снова Yandex Workspace SMTP.
