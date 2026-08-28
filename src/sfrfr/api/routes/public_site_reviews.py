"""Публичные цитаты для витрины + очередь (без рейтинга)."""

from __future__ import annotations

import hashlib
import hmac
import html
import logging
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Form, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from sfrfr.api.routes.public_leads import _require_captcha
from sfrfr.core.config import get_settings
from sfrfr.core.site_reviews import (
    enqueue_quote,
    get_item,
    list_published,
    review_byline,
    set_author_label,
    set_status,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_REVIEW_NOTIFY_EMAIL = "proverkastaza@yandex.ru"
_SITE_REVIEWS_PAGE = "https://proverkastaza.ru/otzyvy/"
_SREV_PUBLISH = "srev:p:"
_SREV_REJECT = "srev:r:"


class SiteReviewSubmit(BaseModel):
    """Короткий отзыв с /otzyvy/: без ФИО, в очередь модерации."""

    text: str = Field(min_length=1, max_length=600)
    consent: bool = Field(description="Согласие на обработку текста отзыва")
    publish_consent: bool = Field(
        default=False,
        description="Отдельное согласие на публикацию цитаты на сайте без ПДн",
    )
    smartcaptcha_token: str | None = Field(default=None, max_length=4000)
    recaptcha_token: str | None = Field(default=None, max_length=4000)
    mail_already_sent: bool = Field(
        default=False,
        description="True если письмо уже отправил CF7 — не дублировать SMTP",
    )
    source: str = Field(default="site", max_length=32)
    author_label: str | None = Field(
        default=None,
        max_length=40,
        description="Подпись на сайте: имя или «имя, город», без фамилии",
    )


class WpMailRelay(BaseModel):
    """Relay wp_mail с WordPress → Яндекс SMTP (без SMTP-плагина на WP)."""

    to: str = Field(min_length=3, max_length=320)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)
    html: str | None = Field(default=None, max_length=40000)


def _trusted_wp_token(x_public_lead_token: str | None) -> bool:
    """WP MU после CF7: тот же PUBLIC_LEAD_TOKEN, что у заявок."""
    expected = (get_settings().public_lead_token or "").strip()
    if not expected or not x_public_lead_token:
        return False
    return x_public_lead_token.strip() == expected


def _moderation_secret() -> str:
    settings = get_settings()
    return (settings.public_lead_token or settings.app_secret_key or "sfrfr").strip()


def moderate_sig(item_id: str, review_status: str) -> str:
    """Короткий HMAC для ссылок в письме (без логина)."""
    raw = f"{item_id}:{review_status}".encode()
    return hmac.new(_moderation_secret().encode(), raw, hashlib.sha256).hexdigest()[:32]


def verify_moderate_sig(item_id: str, review_status: str, sig: str) -> bool:
    expected = moderate_sig(item_id, review_status)
    return hmac.compare_digest(expected, (sig or "").strip())


def moderation_urls(item_id: str) -> dict[str, str]:
    base = (get_settings().public_base_url or "https://api.proverkastaza.ru").rstrip("/")
    pub = moderate_sig(item_id, "published")
    rej = moderate_sig(item_id, "rejected")
    return {
        "published": (
            f"{base}/api/public/site-reviews/moderate"
            f"?id={quote(item_id)}&status=published&sig={pub}"
        ),
        "rejected": (
            f"{base}/api/public/site-reviews/moderate"
            f"?id={quote(item_id)}&status=rejected&sig={rej}"
        ),
    }


def site_review_max_keyboard(item_id: str) -> list[dict[str, Any]]:
    from sfrfr.integrations.max.client import inline_buttons_keyboard

    return inline_buttons_keyboard(
        [
            [
                {
                    "type": "callback",
                    "text": "✅ Одобрить",
                    "payload": f"{_SREV_PUBLISH}{item_id}",
                },
                {
                    "type": "callback",
                    "text": "❌ Отклонить",
                    "payload": f"{_SREV_REJECT}{item_id}",
                },
            ]
        ]
    )


def parse_site_review_callback(payload: str) -> tuple[str, str] | None:
    """Вернуть (item_id, status) или None."""
    raw = (payload or "").strip()
    if raw.startswith(_SREV_PUBLISH):
        return raw[len(_SREV_PUBLISH) :], "published"
    if raw.startswith(_SREV_REJECT):
        return raw[len(_SREV_REJECT) :], "rejected"
    return None


def site_review_public_url(item_id: str) -> str:
    """Ссылка на опубликованный отзыв: query для PHP + hash для прокрутки."""
    rid = (item_id or "").strip()
    if not rid:
        return _SITE_REVIEWS_PAGE
    return f"{_SITE_REVIEWS_PAGE}?review={quote(rid)}#review-{rid}"


def build_site_review_moderation_reply(
    *,
    item_id: str,
    review_status: str,
    quote: str = "",
    ok: bool = True,
    error: str | None = None,
) -> tuple[str, list[dict[str, Any]] | None, str | None]:
    """Текст, кнопка-ссылка и format для MAX после модерации отзыва."""
    from sfrfr.integrations.max.client import inline_link_keyboard

    if not ok:
        if error == "author_label_required":
            return (
                "Не удалось опубликовать: укажите подпись (имя или «имя, город») "
                "и одобрите снова.",
                None,
                None,
            )
        return (f"Не удалось изменить статус: {error or 'ошибка'}.", None, None)

    quote_block = f"\n\nТекст:\n{quote.strip()}" if quote.strip() else ""
    if review_status == "published":
        url = site_review_public_url(item_id)
        text = (
            f"Отзыв опубликован. Проверьте на сайте.{quote_block}\n\n"
            f"[Открыть этот отзыв]({url})"
        )
        attachments = inline_link_keyboard("Открыть этот отзыв", url)
        return text, attachments, "markdown"

    text = (
        f"Отзыв отклонён. Проверьте на сайте.{quote_block}\n\n"
        f"[Страница отзывов]({_SITE_REVIEWS_PAGE})"
    )
    attachments = inline_link_keyboard("Страница отзывов", _SITE_REVIEWS_PAGE)
    return text, attachments, "markdown"


def notify_site_review_queued(
    *,
    text: str,
    item_id: str,
    source: str,
    send_email: bool = True,
    publish_consent: bool = False,
    author_label: str = "",
    client_id: str = "",
) -> dict[str, Any]:
    """Письмо на proverkastaza@yandex.ru (если нужно) + fanout в MAX / канал команды."""
    # Полный текст для сотрудника (лимит формы 600); без обрезки «для превью».
    full_text = (text or "").strip()[:600]
    urls = moderation_urls(item_id)
    mode = (
        "можно опубликовать после проверки"
        if publish_consent
        else "внутренняя обратная связь (без согласия на публикацию)"
    )
    body = (
        "Новый отзыв на сайте\n"
        f"источник: {source}\n"
        f"режим: {mode}\n"
        f"id: {item_id}\n\n"
        f"Текст отзыва:\n{full_text}\n"
    )
    label_line = (author_label or "").strip()
    if publish_consent:
        if label_line:
            body += f"\nПодпись на сайте: {label_line}\n"
        else:
            body += (
                "\nПодпись на сайте: не указана — перед одобрением задайте имя "
                "(имя или «имя, город», без фамилии).\n"
            )
    cid = (client_id or "").strip()
    if cid:
        body += f"client_id: {cid}\n"
    if publish_consent:
        body += (
            f"\nОдобрить: {urls['published']}\n"
            f"Отклонить: {urls['rejected']}"
        )
    else:
        body += "\nНа витрину не ставить без отдельного согласия автора."
    html_body = (
        "<p><b>Новый отзыв на сайте</b></p>"
        f"<p>источник: {html.escape(source)}<br>"
        f"режим: {html.escape(mode)}<br>"
        f"id: <code>{html.escape(item_id)}</code></p>"
        "<p><b>Текст отзыва</b></p>"
        f"<blockquote style=\"margin:0;padding:0.75rem 1rem;background:#f5f7f6;"
        f"border-left:4px solid #1a5c3a;white-space:pre-wrap\">"
        f"{html.escape(full_text)}</blockquote>"
    )
    if publish_consent:
        if label_line:
            html_body += f"<p><b>Подпись на сайте:</b> {html.escape(label_line)}</p>"
        else:
            html_body += (
                "<p><b>Подпись на сайте:</b> "
                "<span style=\"color:#b45309\">не указана — задайте перед одобрением</span></p>"
            )
    if publish_consent:
        html_body += (
            "<p>"
            f'<a href="{html.escape(urls["published"])}">✅ Одобрить на сайте</a>'
            " &nbsp;|&nbsp; "
            f'<a href="{html.escape(urls["rejected"])}">❌ Отклонить</a>'
            "</p>"
        )
    html_body += (
        "<p style=\"color:#666;font-size:12px\">Рейтинг Яндекса эта форма не меняет.</p>"
    )
    out: dict[str, Any] = {"email": None, "max": None}

    if send_email:
        try:
            from sfrfr.integrations.yandex_workspace.mail import send_mail

            out["email"] = send_mail(
                to=_REVIEW_NOTIFY_EMAIL,
                template="custom",
                subject="[Проверка стажа] Отзыв на сайте (модерация)",
                body=body,
                html=html_body,
                from_name="Проверка стажа",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("site review email notify failed: %s", exc)
            out["email"] = {"ok": False, "error": type(exc).__name__}

    try:
        from sfrfr.integrations.max.handler import _fanout_ops_text

        attachments = site_review_max_keyboard(item_id) if publish_consent else None
        _fanout_ops_text(body, attachments=attachments)
        out["max"] = {"ok": True}
    except Exception as exc:  # noqa: BLE001
        logger.warning("site review max notify failed: %s", exc)
        out["max"] = {"ok": False, "error": type(exc).__name__}

    return out


@router.get("/site-reviews")
def public_site_reviews(limit: int = 6) -> dict[str, Any]:
    """Только published — для блока на главной и /otzyvy/."""
    items = list_published(limit=limit)
    return {
        "ok": True,
        "items": items,
        "note": "Рейтинг только на Яндекс Картах; здесь модерируемые цитаты.",
    }


@router.get("/site-reviews/moderate", response_class=HTMLResponse)
def moderate_site_review_link(
    id: str,
    status: str,
    sig: str,
) -> HTMLResponse:
    """Кликабельные ссылки из письма: одобрить / отклонить."""
    item_id = (id or "").strip()
    review_status = (status or "").strip().lower()
    if review_status not in {"published", "rejected"}:
        raise HTTPException(status_code=400, detail="bad_status")
    if not item_id or not verify_moderate_sig(item_id, review_status, sig):
        raise HTTPException(status_code=403, detail="bad_signature")
    item = get_item(item_id) or {}
    quote = str(item.get("text") or "").strip()
    if review_status == "published" and not review_byline(item):
        return _moderation_label_form_page(item_id=item_id, sig=sig, quote=quote)
    result = set_status(item_id, review_status)
    if not result.get("ok"):
        err = str(result.get("error") or "not_found")
        if err == "author_label_required":
            return _moderation_label_form_page(item_id=item_id, sig=sig, quote=quote)
        raise HTTPException(status_code=404, detail=err)
    raw_item = result.get("item")
    item = raw_item if isinstance(raw_item, dict) else {}
    quote = str(item.get("text") or "").strip()
    return _moderation_result_page(
        item_id=item_id,
        review_status=review_status,
        quote=quote,
    )


@router.post("/site-reviews/moderate", response_class=HTMLResponse)
def moderate_site_review_publish_with_label(
    id: str = Form(...),
    status: str = Form(...),
    sig: str = Form(...),
    author_name: str = Form(default=""),
    author_city: str = Form(default=""),
) -> HTMLResponse:
    """Публикация с подписью, если автор не указал имя в форме."""
    item_id = (id or "").strip()
    review_status = (status or "").strip().lower()
    if review_status != "published":
        raise HTTPException(status_code=400, detail="bad_status")
    if not item_id or not verify_moderate_sig(item_id, review_status, sig):
        raise HTTPException(status_code=403, detail="bad_signature")
    item = get_item(item_id) or {}
    quote = str(item.get("text") or "").strip()
    label = _compose_moderation_label(author_name, author_city)
    label_result = set_author_label(item_id, label)
    if not label_result.get("ok"):
        return _moderation_label_form_page(item_id=item_id, sig=sig, quote=quote)
    result = set_status(item_id, review_status)
    if not result.get("ok"):
        err = str(result.get("error") or "not_found")
        return _moderation_result_page(
            item_id=item_id,
            review_status=review_status,
            quote=quote,
            error=err,
        )
    raw_item = result.get("item")
    item = raw_item if isinstance(raw_item, dict) else {}
    quote = str(item.get("text") or "").strip()
    return _moderation_result_page(
        item_id=item_id,
        review_status=review_status,
        quote=quote,
    )


def _moderation_label_form_page(*, item_id: str, sig: str, quote: str) -> HTMLResponse:
    quote_html = (
        f"<blockquote style=\"margin:1rem 0;padding:0.75rem 1rem;background:#f5f7f6;"
        f"border-left:4px solid #1a5c3a;white-space:pre-wrap\">"
        f"{html.escape(quote)}</blockquote>"
        if quote.strip()
        else ""
    )
    page = (
        "<!doctype html><html lang=\"ru\"><meta charset=\"utf-8\">"
        "<title>Подпись отзыва</title>"
        "<body style=\"font-family:sans-serif;max-width:32rem;margin:2rem auto;padding:0 1rem\">"
        "<h1>Укажите подпись для публикации</h1>"
        "<p>На сайте показываем только имя или «имя, город» — без фамилии и контактов.</p>"
        f"{quote_html}"
        "<form method=\"post\" action=\"/api/public/site-reviews/moderate\">"
        f"<input type=\"hidden\" name=\"id\" value=\"{html.escape(item_id)}\">"
        "<input type=\"hidden\" name=\"status\" value=\"published\">"
        f"<input type=\"hidden\" name=\"sig\" value=\"{html.escape(sig)}\">"
        "<p><label>Имя<br>"
        "<input name=\"author_name\" required maxlength=\"24\" "
        "placeholder=\"Например: Сергей\" style=\"width:100%;padding:0.5rem\"></label></p>"
        "<p><label>Город (необязательно)<br>"
        "<input name=\"author_city\" maxlength=\"24\" "
        "placeholder=\"Например: Архангельск\" style=\"width:100%;padding:0.5rem\"></label></p>"
        "<p><button type=\"submit\" "
        "style=\"padding:0.6rem 1.2rem\">Опубликовать на сайте</button></p>"
        "</form>"
        f"<p style=\"color:#666;font-size:12px\">id: <code>{html.escape(item_id)}</code></p>"
        "</body></html>"
    )
    return HTMLResponse(page)


def _compose_moderation_label(name: str, city: str) -> str:
    name = " ".join((name or "").split()).strip()
    city = " ".join((city or "").split()).strip()
    if not name:
        return ""
    if city:
        return f"{name}, {city}"[:40]
    return name[:40]


def _moderation_result_page(
    *,
    item_id: str,
    review_status: str,
    quote: str,
    error: str | None = None,
) -> HTMLResponse:
    if review_status == "published" and not error:
        headline = "Отзыв опубликован. Проверьте на сайте."
        link_url = site_review_public_url(item_id)
        link_label = "Открыть этот отзыв"
    elif review_status == "rejected" and not error:
        headline = "Отзыв отклонён. Проверьте на сайте."
        link_url = _SITE_REVIEWS_PAGE
        link_label = "Страница отзывов"
    else:
        headline = "Не удалось опубликовать"
        link_url = _SITE_REVIEWS_PAGE
        link_label = "Страница отзывов"
    quote_html = (
        f"<blockquote style=\"margin:1rem 0;padding:0.75rem 1rem;background:#f5f7f6;"
        f"border-left:4px solid #1a5c3a;white-space:pre-wrap\">"
        f"{html.escape(quote)}</blockquote>"
        if quote.strip()
        else ""
    )
    err_html = (
        f"<p style=\"color:#b45309\">{html.escape(error or 'ошибка')}</p>"
        if error
        else ""
    )
    page = (
        "<!doctype html><html lang=\"ru\"><meta charset=\"utf-8\">"
        "<title>Модерация отзыва</title>"
        "<body style=\"font-family:sans-serif;max-width:32rem;margin:2rem auto;padding:0 1rem\">"
        f"<h1>{html.escape(headline)}</h1>"
        f"{err_html}"
        f"{quote_html}"
        f"<p><a href=\"{html.escape(link_url)}\">{html.escape(link_label)}</a></p>"
        f"<p style=\"color:#666;font-size:12px\">id: <code>{html.escape(item_id)}</code></p>"
        "</body></html>"
    )
    return HTMLResponse(page)


@router.post("/site-reviews")
def submit_site_review(
    payload: SiteReviewSubmit,
    request: Request,
    x_public_lead_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Поставить цитату в очередь. На рейтинг Яндекса не влияет."""
    if not payload.consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="consent_required",
        )
    trusted = _trusted_wp_token(x_public_lead_token)
    if not trusted:
        client_ip = request.client.host if request.client else None
        _require_captcha(
            recaptcha_token=payload.recaptcha_token,
            smartcaptcha_token=payload.smartcaptcha_token,
            client_ip=client_ip,
        )
    source = (payload.source or "site").strip()[:32] or "site"
    result = enqueue_quote(
        text=payload.text,
        source=source,
        consent=True,
        publish_consent=bool(payload.publish_consent),
        author_label=(payload.author_label or "") if payload.publish_consent else "",
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="consent_required",
        )
    if not result.get("queued"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(result.get("reason") or "rejected"),
        )
    item_id = str(result.get("id") or "")
    author_label = ""
    if payload.publish_consent:
        author_label = (payload.author_label or "").strip()
    notify_site_review_queued(
        text=payload.text,
        item_id=item_id,
        source=source,
        send_email=not payload.mail_already_sent,
        publish_consent=bool(payload.publish_consent),
        author_label=author_label,
    )
    detail = (
        "После модерации появится на странице."
        if payload.publish_consent
        else "Принято как внутренняя обратная связь (без публикации на сайте)."
    )
    return {
        "ok": True,
        "queued": True,
        "id": item_id,
        "status": result.get("status"),
        "detail": detail,
    }


@router.post("/wp-mail-relay")
def wp_mail_relay(
    payload: WpMailRelay,
    x_public_lead_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """WordPress wp_mail → Яндекс SMTP SFRFR (замена SMTP-плагина на WP)."""
    if not _trusted_wp_token(x_public_lead_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    try:
        from sfrfr.integrations.yandex_workspace.mail import send_mail

        result = send_mail(
            to=payload.to,
            template="custom",
            subject=payload.subject,
            body=payload.body,
            html=payload.html,
            from_name="Проверка стажа",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("wp mail relay failed: %s", exc)
        raise HTTPException(status_code=502, detail=type(exc).__name__) from exc
    if not result.get("ok"):
        raise HTTPException(
            status_code=502,
            detail=str(result.get("error") or result.get("reason") or "send_failed"),
        )
    return {"ok": True, "provider": result.get("provider"), "message_id": result.get("message_id")}
