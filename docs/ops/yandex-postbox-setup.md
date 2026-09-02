# Yandex Cloud Postbox — исходящая почта + delivery webhooks

**Дата:** 2026-09-02  
**Связано:** ТЗ-31 (`docs/specs/31-email-delivery-webhooks.md`), SFRFR email delivery

## Зачем

Канон РФ/YC вместо Postmark: письма уходят через **Postbox**, события Delivery/Bounce
попадают в `delivery_events` через HTTPS webhook API.

`delivered` **не** открывает PDF.

## Архитектура

```text
API sfrfr  --SendEmail(SigV4)-->  Postbox
                                      |
                                      v  (configuration set)
                                 Data Streams
                                      |
                                      v
                              Cloud Function
                                      |
                                      v  Basic Auth
                    POST /api/webhooks/email/postbox
                                      |
                                      v
                              delivery_events / notification_jobs
```

## 1. Консоль YC (владелец)

1. Каталог с Postbox: создать **адрес** (From), подтвердить домен (SPF/DKIM по подсказкам консоли).
2. SA с ролью `postbox.sender` (+ viewer при отладке).
3. **Статический ключ доступа** SA → `YANDEX_POSTBOX_ACCESS_KEY_ID` / `YANDEX_POSTBOX_SECRET_ACCESS_KEY`.
4. **Configuration set** → события в **Data Streams**.
5. Cloud Function по триггеру YDS: POST тело уведомления на  
   `https://api.proverkastaza.ru/api/webhooks/email/postbox`  
   с заголовком `Authorization: Basic …` (те же user/pass, что в env).

Пример минимальной CF (Python):

```python
import base64, json, os, urllib.request

WEBHOOK = os.environ["SFRFR_POSTBOX_WEBHOOK_URL"]
AUTH = os.environ["SFRFR_POSTBOX_BASIC"]  # base64(user:pass)

def handler(event, context):
    for msg in event.get("messages") or []:
        details = msg.get("details") or {}
        message = details.get("message") or {}
        raw = message.get("data") or ""
        body = raw if isinstance(raw, (dict, list)) else None
        if body is None and isinstance(raw, str):
            try:
                body = json.loads(base64.b64decode(raw).decode())
            except Exception:
                body = json.loads(raw)
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            WEBHOOK,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Basic {AUTH}",
            },
        )
        urllib.request.urlopen(req, timeout=20)
    return {"ok": True}
```

Доки: [уведомления](https://yandex.cloud/ru/docs/postbox/concepts/notification),  
[webhook tutorial](https://yandex.cloud/ru/docs/postbox/tutorials/postbox-webhook),  
[отправка](https://yandex.cloud/ru/docs/postbox/operations/send-email).

## 2. Env VPS (`/opt/sfrfr/.env`)

```text
YANDEX_POSTBOX_ENABLED=true
YANDEX_POSTBOX_FROM_EMAIL=noreply@proverkastaza.ru
YANDEX_POSTBOX_CONFIGURATION_SET=<имя_или_id_config_set>
YANDEX_POSTBOX_ACCESS_KEY_ID=…
YANDEX_POSTBOX_SECRET_ACCESS_KEY=…
YANDEX_POSTBOX_ENDPOINT=https://postbox.cloud.yandex.net
POSTBOX_WEBHOOK_USER=…
POSTBOX_WEBHOOK_PASSWORD=…
```

Локальная копия секретов webhook: `secrets/yandex-postbox.env` (не в git).

После правок: `chown sfrfr:sfrfr /opt/sfrfr/.env && chmod 600 … && systemctl restart sfrfr-api`.

При `YANDEX_POSTBOX_ENABLED=true` и валидных ключах `send_mail()` идёт в Postbox; иначе — прежний Yandex Workspace SMTP.

## 3. Проверка

```text
GET  https://api.proverkastaza.ru/api/webhooks/email/health
→ yandex_postbox: true, yandex_postbox_send: true

POST https://api.proverkastaza.ru/api/webhooks/email/postbox
Authorization: Basic …
{"eventType":"Delivery","mail":{"messageId":"test-1",…},"delivery":{…},"eventId":"test-1:0"}
→ stored ≥ 1 в delivery_events
```

Симулятор доставки Postbox — для теста без реального ящика (см. docs YC).

## Rollback

`YANDEX_POSTBOX_ENABLED=false` → снова SMTP. Webhook endpoint можно оставить.
