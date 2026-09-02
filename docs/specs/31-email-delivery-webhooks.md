# ТЗ-31: webhook-доставка e-mail ≠ открытие PDF

**Версия:** 1.1  
**Дата:** 2026-09-02  
**Статус:** MVP — **Yandex Cloud Postbox** (канон) + Postmark / Mailgun / SendGrid (резерв)  
**Связано:** [ТЗ-28](28-diagnosis-secure-delivery.md) · [ТЗ-30](30-diagnosis-delivery-triggers.md) · [Postbox notifications](https://yandex.cloud/ru/docs/postbox/concepts/notification) · Ops: [`docs/ops/yandex-postbox-setup.md`](../ops/yandex-postbox-setup.md)

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

| Провайдер | Auth | Endpoint / канал |
|-----------|------|------------------|
| **Yandex Cloud Postbox** (канон) | Send: AWS SigV4; Webhook: HTTP Basic (CF→API) | `POST /api/webhooks/email/postbox` |
| **Yandex SMTP** (fallback) | OAuth2 XOAUTH2 | Workspace `send_mail` |
| **Postmark** (резерв) | HTTP Basic | `POST /api/webhooks/email/postmark` |
| **Mailgun** | HMAC-SHA256(`timestamp`+`token`) + freshness ±5 мин | `POST /api/webhooks/email/mailgun` |
| **SendGrid** | ECDSA по **raw body** + headers Signature/Timestamp | `POST /api/webhooks/email/sendgrid` |

Исходящий канон: **Postbox** при `YANDEX_POSTBOX_ENABLED=true` + ключи; иначе Workspace SMTP.  
Retry SMTP: `POST /api/portal/admin/notification-jobs/smtp-retry` (backoff 15/60/240 мин, max 3).

Не применять один алгоритм ко всем. Health: `GET /api/webhooks/email/health`.

Env (фрагмент):

```text
YANDEX_POSTBOX_ENABLED=true
YANDEX_POSTBOX_FROM_EMAIL=…
YANDEX_POSTBOX_ACCESS_KEY_ID=…
YANDEX_POSTBOX_SECRET_ACCESS_KEY=…
YANDEX_POSTBOX_CONFIGURATION_SET=…
POSTBOX_WEBHOOK_USER=…
POSTBOX_WEBHOOK_PASSWORD=…
POSTMARK_WEBHOOK_USER=…          # резерв
MAILGUN_WEBHOOK_SIGNING_KEY=…
SENDGRID_EVENT_WEBHOOK_PUBLIC_KEY=…
EMAIL_DELIVERY_HASH_SALT=…
```

Postbox события: `Send` → accepted; `Delivery` → delivered; `Bounce` Permanent/Transient → hard/soft;  
`DeliveryDelay` → deferred; `Complaint` / `Subscription` / `Open` / `Click` / `Rendering Failure` — по таблице §5.

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
| accepted/processed / Postbox Send | job → accepted |
| delivered | job → delivered (**не** PDF opened) |
| deferred / soft bounce / DeliveryDelay | temporary_problem; retry-метка |
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
2. Postbox в YC + CF bridge (`docs/ops/yandex-postbox-setup.md`).  
3. Env на VPS → `GET /api/webhooks/email/health` (`yandex_postbox` / `yandex_postbox_send`).  
4. Rollback: `YANDEX_POSTBOX_ENABLED=false`; таблицы оставить.

---

## 8. Приёмка

- [x] Postbox: parse SES-like notifications + YDS wrapper  
- [x] Postbox: SendEmail SigV4 + `provider=yandex_postbox`  
- [x] Postbox webhook: Basic Auth  
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
- [ ] Ops: Postbox identity + CF на prod (чеклист setup)  
