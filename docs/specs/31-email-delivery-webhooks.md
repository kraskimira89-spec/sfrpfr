# ТЗ-31: webhook-доставка e-mail ≠ открытие PDF

**Версия:** 1.0  
**Дата:** 2026-08-23  
**Статус:** MVP — Postmark / Mailgun / SendGrid webhooks + журнал `delivery_events`  
**Связано:** [ТЗ-28](28-diagnosis-secure-delivery.md) · [ТЗ-30](30-diagnosis-delivery-triggers.md) · [Mailgun securing](https://documentation.mailgun.com/docs/mailgun/user-manual/webhooks/securing-webhooks) · [SendGrid Event Webhook security](https://www.twilio.com/docs/sendgrid/for-developers/tracking-events/getting-started-event-webhook-security-features)

---

## 1. Принцип

| Событие | Значение |
|--------|----------|
| `email delivered` | Письмо принято **почтовым сервером** получателя |
| `email opened` | Tracking-пиксель (ненадёжно) — **только аналитика** |
| `diagnostic_result opened` | Клиент открыл PDF в кабинете / secure link |

`delivered` **не** переводит PDF в `opened`.

---

## 2. Провайдеры (схемы подписи разные)

| Провайдер | Auth | Endpoint |
|-----------|------|----------|
| **Yandex SMTP** (исходящая диагностика) | OAuth2 XOAUTH2 | исходящий `send_mail` → Message-ID в job |
| **Postmark** | HTTP Basic | `POST /api/webhooks/email/postmark` |
| **Mailgun** | HMAC-SHA256(`timestamp`+`token`) + freshness ±5 мин | `POST /api/webhooks/email/mailgun` |
| **SendGrid** | ECDSA по **raw body** + headers Signature/Timestamp | `POST /api/webhooks/email/sendgrid` |

Исходящий канон MVP: **Yandex SMTP**. Webhooks ESP — optional (если письмо ушло через этот ESP).  
Retry SMTP: `POST /api/portal/admin/notification-jobs/smtp-retry` (backoff 15/60/240 мин, max 3).

Не применять один алгоритм ко всем. Health: `GET /api/webhooks/email/health`.

Env:

```text
POSTMARK_WEBHOOK_USER=…
POSTMARK_WEBHOOK_PASSWORD=…
MAILGUN_WEBHOOK_SIGNING_KEY=…          # HTTP webhook signing key
SENDGRID_EVENT_WEBHOOK_PUBLIC_KEY=…  # base64 DER или PEM
EMAIL_DELIVERY_HASH_SALT=…
```

**Рекомендация MVP (Python):** Mailgun — простая HMAC-проверка.  
Если уже SendGrid — только raw body + ECDSA.  
Postmark остаётся вариантом с Basic Auth.

Исходящая почта диагностики пока может идти через **Yandex SMTP** (`Message-ID` в `notification_jobs.provider_message_id`).

---

## 3. Статусы

```text
PDF:  published → link_issued → opened → …
Email job: draft → approved → queued → sent/accepted → delivered
           ↘ deferred / soft_bounce (retry)
           ↘ hard_bounce / failed / cancelled
```

---

## 4. Таблицы

- `delivery_events` — fingerprint, redacted JSON, без полного e-mail/PDF/ПДн  
- `contact_delivery_status` — техстоп канала (≠ отзыв ПДн)  
- поля `notification_jobs`: provider, provider_message_id, recipient_domain, *_at, error_*

---

## 5. Переходы

| Webhook | Действие |
|--------|----------|
| accepted/processed | job → accepted |
| delivered | job → delivered (**не** PDF opened) |
| deferred / soft bounce | temporary_problem; retry-метка |
| hard bounce | block channel; cancel pending email; задача сотруднику |
| complaint | block; cancel; security-задача |
| unsubscribe | marketing consent revoked (email only) |
| open / click | только запись в journal |

Идемпотентность: `event_fingerprint` SHA-256.

---

## 6. Dashboard

`GET /api/portal/admin/email-delivery/dashboard` — counts + unmatched (staff).

---

## 7. Rollout / rollback

1. Миграция `20260823230000_email_delivery_webhooks.sql` (SFRFR).  
2. Env на VPS: ключи выбранного провайдера (`POSTMARK_*` / `MAILGUN_*` / `SENDGRID_*`).  
3. Webhook в кабинете провайдера → `GET /api/webhooks/email/health`.  
4. Rollback: отключить webhook у провайдера; таблицы оставить.

---

## 8. Приёмка

- [x] Postmark: Basic Auth до разбора payload  
- [x] Mailgun: HMAC-SHA256(timestamp+token) + freshness ±5 мин  
- [x] SendGrid: ECDSA по raw body + Signature/Timestamp headers  
- [x] Идемпотентность fingerprint  
- [x] delivered ≠ PDF opened  
- [x] hard/soft bounce различие  
- [x] unmatched message_id  
- [x] redaction e-mail/UUID из payload  
- [x] P1 (Yandex): SMTP retry worker (`smtp-retry`, backoff)  
- [ ] P2: IMAP DSN → delivery_events (optional)  
- [ ] P2: отправка через API ESP (если сменим исходящий канал)  
