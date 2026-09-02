"""Публичные страницы сервисных опросов (ТЗ-29 P1): e-mail confirm, не GET-fix."""

from __future__ import annotations

import html
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from sfrfr.db.diagnosis_survey_repository import DiagnosisSurveyRepository
from sfrfr.services.diagnosis_survey import (
    DiagnosisSurveyService,
    _answers_for_type,
    _body_for_type,
    hash_action_token,
)

logger = logging.getLogger(__name__)
router = APIRouter()


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
    p {{ font-size: 1.05rem; color: var(--muted); }}
    .card {{ background: var(--card); border-radius: 12px; padding: 1.25rem;
      box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
    .choice {{ font-size: 1.1rem; color: var(--ink); font-weight: 600; margin: 1rem 0; }}
    button {{ display: inline-flex; align-items: center; justify-content: center;
      width: 100%; min-height: 48px; margin-top: .75rem; border: 0; border-radius: 10px;
      background: var(--accent); color: #fff; font-size: 1.1rem; font-weight: 600; cursor: pointer; }}
    .hint {{ font-size: .95rem; margin-top: 1rem; }}
    .ok {{ color: var(--ok); }}
    .warn {{ color: var(--danger); }}
  </style>
</head>
<body>
  <main><div class="card">{body}</div></main>
</body>
</html>"""


def _wants_html(request: Request) -> bool:
    accept = (request.headers.get("accept") or "").lower()
    if "application/json" in accept and "text/html" not in accept:
        return False
    if "text/html" in accept:
        return True
    return "application/json" not in accept


def _load_token_context(raw: str) -> tuple[dict, dict, str, str]:
    token_hash = hash_action_token(raw)
    row = DiagnosisSurveyRepository().get_token_by_hash(token_hash)
    if not row:
        raise LookupError("invalid_token")
    campaign = DiagnosisSurveyRepository().get_campaign(str(row["campaign_id"]))
    if not campaign:
        raise LookupError("campaign_missing")
    survey_type = str(campaign.get("survey_type") or "clarity")
    answer = str(row["answer_code"])
    labels = _answers_for_type(survey_type)
    label = labels.get(answer, answer)
    return campaign, row, survey_type, label


def _render_confirm(*, token: str, survey_type: str, label: str, body_text: str) -> str:
    title = "Подтвердите ответ"
    intro = html.escape(body_text)
    choice = html.escape(label)
    safe_token = html.escape(token)
    inner = f"""
    <h1>{html.escape(title)}</h1>
    <p>{intro}</p>
    <p class="choice">Ваш вариант: {choice}</p>
    <form method="post" action="/api/portal/survey/{safe_token}/confirm">
      <button type="submit">Подтвердить</button>
    </form>
    <p class="hint">Ответ сохранится только после нажатия кнопки. Сканы и персональные данные в чат не отправляйте.</p>
    """
    if survey_type == "first_step":
        page_title = "Первый шаг плана"
    elif survey_type == "acquaint":
        page_title = "Ознакомление с результатом"
    else:
        page_title = "Понятность результата"
    return _page_shell(title=page_title, body=inner)


def _render_done(message: str) -> str:
    return _page_shell(
        title="Спасибо",
        body=f"<h1>Спасибо</h1><p class='ok'>{html.escape(message)}</p>",
    )


def _render_error(detail: str) -> str:
    return _page_shell(
        title="Ссылка недоступна",
        body=(
            f"<h1>Ссылка недоступна</h1>"
            f"<p class='warn'>{html.escape(detail)}</p>"
            "<p class='hint'>Напишите в чат MAX или на почту — поможем.</p>"
        ),
    )


@router.get("/survey/{token}", response_model=None)
def open_survey_confirm(token: str, request: Request) -> Response:
    raw = (token or "").strip()
    if len(raw) < 10:
        raise HTTPException(status_code=404, detail="not_found")
    try:
        campaign, _row, survey_type, label = _load_token_context(raw)
    except LookupError:
        if _wants_html(request):
            return HTMLResponse(_render_error("Ссылка недействительна или уже использована."), status_code=404)
        raise HTTPException(status_code=404, detail="invalid_token") from None

    body_text = _body_for_type(survey_type, campaign)
    if not _wants_html(request):
        return JSONResponse(
            {
                "survey_type": survey_type,
                "answer_label": label,
                "body": body_text,
                "confirm_url": f"/api/portal/survey/{raw}/confirm",
            },
            headers={"Cache-Control": "no-store, private"},
        )
    return HTMLResponse(
        _render_confirm(token=raw, survey_type=survey_type, label=label, body_text=body_text),
        headers={"Cache-Control": "no-store, private", "X-Robots-Tag": "noindex"},
    )


@router.post("/survey/{token}/confirm", response_model=None)
async def post_survey_confirm(token: str, request: Request) -> Response:
    raw = (token or "").strip()
    if len(raw) < 10:
        raise HTTPException(status_code=404, detail="not_found")
    try:
        campaign, _row, survey_type, _label = _load_token_context(raw)
        channel = str(campaign.get("channel") or "email")
        out = DiagnosisSurveyService().handle_action_token(
            raw,
            channel=channel,
            confirmation_method="email_confirm",
        )
    except LookupError:
        if _wants_html(request):
            return HTMLResponse(_render_error("Ссылка недействительна."), status_code=404)
        raise HTTPException(status_code=404, detail="invalid_token") from None
    except PermissionError:
        if _wants_html(request):
            return HTMLResponse(_render_error("Срок ответа истёк."), status_code=410)
        raise HTTPException(status_code=410, detail="expired") from None

    message = str(out.get("text") or "Ответ принят. Спасибо!")
    logger.info(
        "survey_email_confirm type=%s idempotent=%s",
        survey_type,
        out.get("idempotent"),
    )
    if _wants_html(request):
        return HTMLResponse(
            _render_done(message),
            headers={"Cache-Control": "no-store, private", "X-Robots-Tag": "noindex"},
        )
    return JSONResponse(out, headers={"Cache-Control": "no-store, private"})
