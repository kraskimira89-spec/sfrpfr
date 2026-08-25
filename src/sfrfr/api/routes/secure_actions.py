"""Публичные secure action pages (Sprint 2): consent + view_pdf. Без JWT."""

from __future__ import annotations

import html
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from sfrfr.core.config import get_settings
from sfrfr.secure_links.actions import (
    grant_consent_via_token,
    load_context,
    resolve_pdf_signed_url,
)
from sfrfr.secure_links.errors import SecureLinkDenied, SecureLinksDisabled
from sfrfr.security.auth import Principal, require_staff
from sfrfr.security.integrations import SIGNED_URL_TTL_SECONDS

logger = logging.getLogger(__name__)

router = APIRouter()


class SecureConsentBody(BaseModel):
    accepted: bool = Field(..., description="Клиент подтвердил согласие")


class IssueSecureLinkBody(BaseModel):
    purpose: str = Field(..., pattern="^(consent|view_pdf)$")
    document_id: str | None = None
    diagnostic_result_id: str | None = None
    ttl_hours: int | None = Field(default=None, ge=1, le=168)
    max_uses: int | None = Field(default=None, ge=1, le=10)


def _http_for(exc: Exception) -> HTTPException:
    if isinstance(exc, SecureLinksDisabled):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    if isinstance(exc, SecureLinkDenied):
        code = status.HTTP_410_GONE if exc.reason in (
            "expired",
            "revoked",
            "consumed",
            "superseded",
            "max_uses",
        ) else status.HTTP_404_NOT_FOUND
        return HTTPException(status_code=code, detail=exc.reason)
    return HTTPException(status_code=500, detail="secure_action_error")


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _wants_html(request: Request) -> bool:
    accept = (request.headers.get("accept") or "").lower()
    if "application/json" in accept and "text/html" not in accept:
        return False
    if "text/html" in accept:
        return True
    # браузер без Accept → HTML
    return "application/json" not in accept


def _page_shell(*, title: str, body: str) -> str:
    safe_title = html.escape(title)
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <meta name="robots" content="noindex,nofollow,noarchive"/>
  <title>{safe_title}</title>
  <style>
    :root {{ --ink:#1a2332; --muted:#5a6577; --bg:#f4f6f9; --card:#fff;
      --accent:#1e4d8c; --danger:#b42318; --ok:#0f6b3c; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: var(--bg); color: var(--ink); line-height: 1.45; }}
    main {{ max-width: 28rem; margin: 0 auto; padding: 1.25rem 1rem 2.5rem; }}
    h1 {{ font-size: 1.45rem; margin: 0 0 .75rem; }}
    p, li {{ font-size: 1.05rem; color: var(--muted); }}
    .card {{ background: var(--card); border-radius: 12px; padding: 1.25rem;
      box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
    label {{ display: flex; gap: .75rem; align-items: flex-start; margin: 1rem 0;
      font-size: 1.05rem; color: var(--ink); }}
    input[type=checkbox] {{ width: 1.25rem; height: 1.25rem; margin-top: .2rem; flex-shrink: 0; }}
    a {{ color: var(--accent); }}
    button, .btn {{ display: inline-flex; align-items: center; justify-content: center;
      width: 100%; min-height: 48px; margin-top: .75rem; border: 0; border-radius: 10px;
      background: var(--accent); color: #fff; font-size: 1.1rem; font-weight: 600;
      text-decoration: none; cursor: pointer; }}
    button:disabled {{ opacity: .5; cursor: not-allowed; }}
    .warn {{ color: var(--danger); font-size: .95rem; }}
    .ok {{ color: var(--ok); }}
    .hint {{ font-size: .95rem; margin-top: 1rem; }}
  </style>
</head>
<body>
  <main><div class="card">{body}</div></main>
</body>
</html>"""


def _render_consent(ctx: dict[str, Any], token: str, *, error: str | None = None) -> str:
    if ctx.get("consent_already"):
        inner = (
            f"<h1>{html.escape(ctx['title'])}</h1>"
            "<p class='ok'>Согласие уже принято.</p>"
            f"<p class='hint'>{html.escape(ctx['hint'])}</p>"
        )
        return _page_shell(title=ctx["title"], body=inner)

    err = f"<p class='warn'>{html.escape(error)}</p>" if error else ""
    links = ctx.get("links") or {}
    consent_href = html.escape(links.get("consent") or "#")
    pdn_href = html.escape(links.get("pdn") or "#")
    inner = f"""
    <h1>{html.escape(ctx["title"])}</h1>
    <p>{html.escape(ctx["hint"])}</p>
    {err}
    <form method="post" action="/api/portal/secure/{html.escape(token)}/consent">
      <label>
        <input type="checkbox" name="accepted" value="1" required />
        <span>Даю согласие на обработку персональных данных и документов
        для подготовки диагностики.
        <a href="{consent_href}" target="_blank" rel="noopener">Текст согласия</a>,
        <a href="{pdn_href}" target="_blank" rel="noopener">политика ПДн</a>.
        </span>
      </label>
      <button type="submit">Подтвердить согласие</button>
    </form>
    <p class="hint">Регистрация и пароль не нужны. Сканы в чат не отправляйте.</p>
    """
    return _page_shell(title=ctx["title"], body=inner)


def _render_view_pdf(ctx: dict[str, Any], token: str) -> str:
    inner = f"""
    <h1>{html.escape(ctx["title"])}</h1>
    <p>{html.escape(ctx["hint"])}</p>
    <a class="btn" href="/api/portal/secure/{html.escape(token)}/pdf">Открыть PDF</a>
    <p class="hint">Ссылка ограничена по сроку. Не пересылайте файл в открытые чаты.</p>
    """
    return _page_shell(title=ctx["title"], body=inner)


def _render_done(message: str) -> str:
    return _page_shell(
        title="Готово",
        body=f"<h1>Готово</h1><p class='ok'>{html.escape(message)}</p>",
    )


def _render_error(detail: str, code: int) -> str:
    title = "Ссылка недоступна" if code >= 400 else "Ошибка"
    return _page_shell(
        title=title,
        body=(
            f"<h1>{html.escape(title)}</h1>"
            f"<p class='warn'>{html.escape(detail)}</p>"
            "<p class='hint'>Вернитесь в чат MAX и запросите новую ссылку у сотрудника.</p>"
        ),
    )


@router.get("/secure/{token}")
def open_secure_action(token: str, request: Request) -> Response:
    raw = (token or "").strip()
    if len(raw) < 20:
        raise HTTPException(status_code=404, detail="not found")
    try:
        ctx = load_context(raw, user_agent=request.headers.get("user-agent"))
    except (SecureLinksDisabled, SecureLinkDenied) as exc:
        http_exc = _http_for(exc)
        if _wants_html(request):
            return HTMLResponse(
                _render_error(str(http_exc.detail), http_exc.status_code),
                status_code=http_exc.status_code,
                headers={"Cache-Control": "no-store, private", "X-Robots-Tag": "noindex"},
            )
        raise http_exc from exc

    if not _wants_html(request):
        return JSONResponse(ctx, headers={"Cache-Control": "no-store, private"})

    purpose = ctx.get("purpose")
    if purpose == "consent":
        body = _render_consent(ctx, raw)
    elif purpose == "view_pdf":
        body = _render_view_pdf(ctx, raw)
    else:
        body = _render_error("Это действие пока недоступно по ссылке.", 400)
    return HTMLResponse(
        body,
        headers={
            "Cache-Control": "no-store, private",
            "X-Robots-Tag": "noindex, nofollow, noarchive",
        },
    )


@router.post("/secure/{token}/consent")
async def post_secure_consent(token: str, request: Request) -> Response:
    raw = (token or "").strip()
    if len(raw) < 20:
        raise HTTPException(status_code=404, detail="not found")

    accepted = False
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        data = await request.json()
        accepted = bool(data.get("accepted"))
    else:
        form = await request.form()
        accepted = str(form.get("accepted") or "") in ("1", "true", "on", "yes")

    if not accepted:
        try:
            ctx = load_context(raw, user_agent=request.headers.get("user-agent"))
        except (SecureLinksDisabled, SecureLinkDenied) as exc:
            raise _http_for(exc) from exc
        if _wants_html(request):
            return HTMLResponse(
                _render_consent(ctx, raw, error="Отметьте согласие, чтобы продолжить."),
                status_code=400,
                headers={"Cache-Control": "no-store, private"},
            )
        raise HTTPException(status_code=400, detail="accepted_required")

    try:
        result = grant_consent_via_token(
            raw,
            ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except (SecureLinksDisabled, SecureLinkDenied) as exc:
        raise _http_for(exc) from exc

    if _wants_html(request) or "application/json" not in content_type:
        return HTMLResponse(
            _render_done(str(result["message"])),
            headers={"Cache-Control": "no-store, private", "X-Robots-Tag": "noindex"},
        )
    return JSONResponse(result, headers={"Cache-Control": "no-store, private"})


@router.get("/secure/{token}/pdf")
def open_secure_pdf(token: str, request: Request) -> Response:
    raw = (token or "").strip()
    if len(raw) < 20:
        raise HTTPException(status_code=404, detail="not found")
    try:
        resolved = resolve_pdf_signed_url(
            raw,
            user_agent=request.headers.get("user-agent"),
            signed_ttl_seconds=SIGNED_URL_TTL_SECONDS,
        )
    except (SecureLinksDisabled, SecureLinkDenied) as exc:
        raise _http_for(exc) from exc

    if resolved.get("bot_skipped"):
        return Response(status_code=204)

    return RedirectResponse(url=str(resolved["url"]), status_code=302)


@router.post("/admin/cases/{case_id}/secure-links", status_code=status.HTTP_201_CREATED)
def admin_issue_secure_link(
    case_id: str,
    body: IssueSecureLinkBody,
    principal: Principal = Depends(require_staff),
) -> dict[str, Any]:
    """Staff: выдать consent или view_pdf (raw_token только в ответе один раз)."""
    settings = get_settings()
    if not settings.secure_action_links_enabled:
        raise HTTPException(status_code=503, detail="secure_action_links_disabled")

    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.secure_links.actions import issue_consent_link, issue_view_pdf_link

    CaseRepository().require_case(principal, case_id)
    try:
        if body.purpose == "consent":
            issued = issue_consent_link(
                case_id=case_id,
                issued_via="staff",
                actor=principal.user_id,
            )
        else:
            if not settings.secure_result_view_enabled:
                raise HTTPException(status_code=503, detail="secure_result_view_disabled")
            issued = issue_view_pdf_link(
                case_id=case_id,
                document_id=body.document_id,
                diagnostic_result_id=body.diagnostic_result_id,
                issued_via="staff",
                actor=principal.user_id,
            )
    except SecureLinkDenied as exc:
        raise HTTPException(status_code=400, detail=exc.reason) from exc
    except SecureLinksDisabled as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Не логируем raw_token
    logger.info(
        "secure_link_issued purpose=%s case=%s prefix=%s by=%s",
        body.purpose,
        case_id[:8],
        issued.get("token_prefix"),
        (principal.user_id or "")[:8],
    )
    return issued
