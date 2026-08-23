from pathlib import Path

import typer

from sfrfr.models.case_status import CaseStatus, status_label_ru

app = typer.Typer(help="SFRFR CLI — аудит пенсионных дел")


@app.command()
def version() -> None:
    """Показать версию пакета."""
    from sfrfr import __version__

    typer.echo(__version__)


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Запустить API."""
    import uvicorn

    uvicorn.run("sfrfr.api:app", host=host, port=port, reload=True)


@app.command("case-create")
def case_create(
    client_name: str = typer.Option(..., "--name", "-n"),
    snils: str = typer.Option("***-***-*** **", "--snils"),
) -> None:
    """Создать кейс (in-memory store процесса CLI)."""
    from sfrfr.core.case_store import get_case_store

    record = get_case_store().create(client_name=client_name, snils_masked=snils)
    typer.echo(f"{record.case_id}\t{status_label_ru(record.ctx.status)}")


@app.command("case-upload")
def case_upload(
    case_id: str = typer.Argument(...),
    path: str = typer.Argument(..., help="Путь к pdf/png/txt"),
) -> None:
    """Загрузить документ в кейс."""
    from pathlib import Path

    from sfrfr.core.case_store import get_case_store
    from sfrfr.storage.local import save_upload

    store = get_case_store()
    try:
        store.require(case_id)
    except KeyError as exc:
        raise typer.BadParameter(f"case not found: {case_id}") from exc

    src = Path(path)
    if not src.exists():
        raise typer.BadParameter(f"file not found: {path}")

    saved = save_upload(case_id, src.name, src.read_bytes())
    record = store.add_document(case_id, str(saved))
    typer.echo(
        f"{record.case_id}\t{status_label_ru(record.ctx.status)}\t"
        f"docs={len(record.ctx.document_paths)}"
    )


@app.command("case-advance")
def case_advance(case_id: str = typer.Argument(...)) -> None:
    """Один шаг пайплайна."""
    from sfrfr.core.case_store import get_case_store

    store = get_case_store()
    try:
        record, result = store.advance(case_id)
    except KeyError as exc:
        raise typer.BadParameter(f"case not found: {case_id}") from exc
    typer.echo(f"ok={result.ok}\t{status_label_ru(result.status)}\t{result.message}")


@app.command("case-run")
def case_run(
    case_id: str = typer.Argument(...),
    stop_at: CaseStatus = typer.Option(CaseStatus.HUMAN_REVIEW, "--stop-at"),
) -> None:
    """Прогнать пайплайн до stop_at."""
    from sfrfr.core.case_store import get_case_store

    store = get_case_store()
    try:
        store.require(case_id)
    except KeyError as exc:
        raise typer.BadParameter(f"case not found: {case_id}") from exc

    record = store.run_until(case_id, stop_at=stop_at)
    typer.echo(
        f"{record.case_id}\t{status_label_ru(record.ctx.status)}\t"
        f"находок={len(record.ctx.findings)}\t"
        f"обоснование={'да' if record.ctx.analysis_notes else 'нет'}\t"
        f"черновик={'да' if record.ctx.draft else 'нет'}"
    )


@app.command("case-complete")
def case_complete(case_id: str = typer.Argument(...)) -> None:
    """Завершить после human_review."""
    from sfrfr.core.case_store import get_case_store

    store = get_case_store()
    try:
        record, result = store.complete(case_id)
    except KeyError as exc:
        raise typer.BadParameter(f"case not found: {case_id}") from exc
    typer.echo(f"ok={result.ok}\t{status_label_ru(record.ctx.status)}\t{result.message}")


@app.command("case-show")
def case_show(case_id: str = typer.Argument(...)) -> None:
    """Показать статус кейса."""
    from sfrfr.core.case_store import get_case_store

    store = get_case_store()
    try:
        record = store.require(case_id)
    except KeyError as exc:
        raise typer.BadParameter(f"case not found: {case_id}") from exc
    ctx = record.ctx
    typer.echo(
        f"id={record.case_id}\n"
        f"этап={status_label_ru(ctx.status)}\n"
        f"документов={len(ctx.document_paths)}\n"
        f"распознано={len(ctx.ocr_texts)}\n"
        f"находок={len(ctx.findings)}\n"
        f"обоснование={'да' if ctx.analysis_notes else 'нет'}\n"
        f"ошибка={ctx.error or '-'}"
    )


@app.command("knowledge-import")
def knowledge_import(
    path: str = typer.Argument(..., help="Диалог: md/txt/json/html (без полных ПДн)"),
    cases_dir: str | None = typer.Option(
        None, "--cases-dir", help="Каталог knowledge/cases"
    ),
) -> None:
    """Импорт диалога → draft-кейс (обезличивание + эвристики)."""
    from pathlib import Path

    from sfrfr.ai.knowledge import KnowledgeCaseRegistry, import_dialog_to_case

    registry = KnowledgeCaseRegistry(Path(cases_dir) if cases_dir else None)
    case = import_dialog_to_case(Path(path), registry=registry)
    typer.echo(
        f"{case.case_id}\tquality={case.quality.value}\t"
        f"problem={case.problem_type}\tdocs={len(case.documents)}"
    )


@app.command("knowledge-depersonalize-dir")
def knowledge_depersonalize_dir(
    inbox: str = typer.Argument(..., help="Каталог с сырыми текстами (вне git)"),
    out: str = typer.Option(..., "--out", "-o", help="Куда писать очищенные файлы"),
    client_name: str | None = typer.Option(
        None, "--client-name", help="Известное ФИО для точечной замены"
    ),
    recursive: bool = typer.Option(True, "--recursive/--flat", help="Обход подпапок"),
) -> None:
    """Пакетно обезличить md/txt/json/html/csv → --out (PDF/сканы пропускаются)."""
    from pathlib import Path

    from sfrfr.ai.knowledge import depersonalize_dir

    inbox_path = Path(inbox)
    if not inbox_path.is_dir():
        raise typer.BadParameter(f"not a directory: {inbox}")

    results = depersonalize_dir(
        inbox_path,
        Path(out),
        client_name=client_name,
        recursive=recursive,
    )
    ok = sum(1 for r in results if r.status == "ok")
    skipped = sum(1 for r in results if r.status == "skipped")
    errors = sum(1 for r in results if r.status == "error")
    for r in results:
        if r.status == "ok" and r.output is not None:
            typer.echo(f"ok\t{r.source.name}\t→\t{r.output}")
        elif r.status == "skipped":
            typer.echo(f"skip\t{r.source.name}\t{r.detail}")
        else:
            typer.echo(f"error\t{r.source.name}\t{r.detail}", err=True)
    typer.echo(f"summary\to={ok}\tskipped={skipped}\terrors={errors}")


@app.command("knowledge-import-deepseek")
def knowledge_import_deepseek(
    conversations: str = typer.Argument(..., help="Путь к conversations.json из экспорта"),
    limit: int = typer.Option(5, "--limit", "-n", help="Сколько пенсионных диалогов"),
    all_matches: bool = typer.Option(
        False, "--all", help="Все совпадения по title (игнор --limit)"
    ),
    cleaned_dir: str | None = typer.Option(
        None, "--cleaned-dir", help="Куда писать обезличенные .md"
    ),
    cases_dir: str | None = typer.Option(None, "--cases-dir"),
) -> None:
    """Импорт пенсионных диалогов из экспорта DeepSeek → draft-кейсы."""
    from pathlib import Path

    from sfrfr.ai.knowledge import KnowledgeCaseRegistry, import_deepseek_conversations

    path = Path(conversations)
    if not path.is_file():
        raise typer.BadParameter(f"file not found: {conversations}")

    registry = KnowledgeCaseRegistry(Path(cases_dir) if cases_dir else None)
    cases = import_deepseek_conversations(
        path,
        registry=registry,
        cleaned_dir=Path(cleaned_dir) if cleaned_dir else None,
        limit=None if all_matches else limit,
    )
    for case in cases:
        typer.echo(
            f"{case.case_id}\t{case.quality.value}\t{case.source_file}\t{case.problem_type}"
        )
    typer.echo(f"imported\t{len(cases)}")


@app.command("knowledge-list")
def knowledge_list(
    quality: str | None = typer.Option(None, "--quality", "-q"),
    rag_ready: bool = typer.Option(False, "--rag-ready", help="Только verified/template"),
    cases_dir: str | None = typer.Option(None, "--cases-dir"),
) -> None:
    """Список обезличенных кейсов базы знаний."""
    from pathlib import Path

    from sfrfr.ai.knowledge import KnowledgeCaseRegistry
    from sfrfr.ai.schemas.knowledge_case import KnowledgeQuality

    registry = KnowledgeCaseRegistry(Path(cases_dir) if cases_dir else None)
    q = KnowledgeQuality(quality) if quality else None
    for case in registry.list_cases(quality=q, rag_ready_only=rag_ready):
        typer.echo(
            f"{case.case_id}\t{case.quality.value}\t"
            f"{case.sfr_outcome.value}\t{case.problem_type}"
        )


@app.command("knowledge-set-status")
def knowledge_set_status(
    case_id: str = typer.Argument(...),
    quality: str = typer.Argument(..., help="draft|verified|rejected|template"),
    cases_dir: str | None = typer.Option(None, "--cases-dir"),
) -> None:
    """Статус качества кейса (в RAG только verified/template)."""
    from pathlib import Path

    from sfrfr.ai.knowledge import KnowledgeCaseRegistry
    from sfrfr.ai.schemas.knowledge_case import KnowledgeQuality

    registry = KnowledgeCaseRegistry(Path(cases_dir) if cases_dir else None)
    try:
        case = registry.set_quality(case_id, KnowledgeQuality(quality))
    except KeyError as exc:
        raise typer.BadParameter(f"case not found: {case_id}") from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"{case.case_id}\tquality={case.quality.value}\tverified_at={case.verified_at}")


@app.command("max-subscribe")
def max_subscribe(
    url: str | None = typer.Option(
        None,
        "--url",
        help="HTTPS webhook; по умолчанию PUBLIC_BASE_URL + /api/integrations/max/webhook",
    ),
) -> None:
    """Зарегистрировать webhook бота MAX (в т.ч. bot_added для chat_id канала)."""
    from sfrfr.core.config import get_settings
    from sfrfr.integrations.max.client import MaxBotClient

    settings = get_settings()
    webhook = url or f"{settings.public_base_url.rstrip('/')}/api/integrations/max/webhook"
    if not webhook.startswith("https://"):
        raise typer.BadParameter("MAX требует HTTPS webhook")
    client = MaxBotClient()
    if not client.available:
        raise typer.BadParameter("Задайте MAX_BOT_TOKEN в .env")
    result = client.subscribe_webhook(webhook)
    typer.echo(f"subscribed\t{webhook}\t{result}")
    typer.echo(
        "Next: add bot as channel admin, then check webhook logs "
        "for max_channel_chat_id_seen / action=bot_added "
        "or run: sfrfr max-channel-info"
    )


@app.command("max-ops-webhook-set")
def max_ops_webhook_set(
    url: str | None = typer.Option(
        None,
        "--url",
        help="HTTPS webhook; по умолчанию …/api/integrations/max/ops/webhook",
    ),
) -> None:
    """Зарегистрировать webhook ops-бота MAX (ТЗ-25)."""
    from sfrfr.core.config import get_settings
    from sfrfr.integrations.max.ops_bot import get_ops_bot, ops_bot_configured

    settings = get_settings()
    webhook = url or f"{settings.public_base_url.rstrip('/')}/api/integrations/max/ops/webhook"
    if not webhook.startswith("https://"):
        raise typer.BadParameter("MAX требует HTTPS webhook")
    if not ops_bot_configured():
        raise typer.BadParameter("Задайте MAX_OPS_BOT_TOKEN в .env")
    client = get_ops_bot()
    secret = (settings.max_ops_webhook_secret or settings.max_webhook_secret or "").strip() or None
    result = client.subscribe_webhook(webhook, secret=secret)
    typer.echo(f"ops_subscribed\t{webhook}\t{result}")
    typer.echo("Next: staff open ops bot → Start; check STAFF_LOGIN_APPROVER_MAX_USER_IDS")


@app.command("max-channel-info")
def max_channel_info(
    remote: bool = typer.Option(
        True,
        "--remote/--local",
        help="Читать discovered с PUBLIC_BASE_URL (webhook пишет на VPS, не в локальный var/)",
    ),
) -> None:
    """Показать URL канала, MAX_CHANNEL_CHAT_ID и обнаруженные chat_id из webhook."""
    import json

    import httpx

    from sfrfr.core.config import get_settings
    from sfrfr.integrations.max.channel_ids import list_known, store_path
    from sfrfr.integrations.max.ssl_context import max_ssl_verify

    settings = get_settings()
    payload: dict[str, object] = {
        "max_channel_url": settings.max_channel_url,
        "max_channel_chat_id": settings.max_channel_chat_id or None,
        "local_store_path": str(store_path()),
        "local_discovered": list_known(),
        "note": (
            "Webhook events are saved on the API server (PUBLIC_BASE_URL), "
            "not in local var/. Use --remote (default) after bot_added."
        ),
    }
    if remote:
        # Legacy host may 301 -> api.proverkastaza.ru; prefer canonical if redirected.
        base = settings.public_base_url.rstrip("/")
        if "taxi-doroga-dobra.ru" in base:
            base = "https://api.proverkastaza.ru"
        url = f"{base}/api/integrations/max/channel-ids"
        headers: dict[str, str] = {}
        if settings.ops_monitor_token:
            headers["X-Ops-Token"] = settings.ops_monitor_token
        elif settings.max_webhook_secret:
            headers["X-Max-Bot-Api-Secret"] = settings.max_webhook_secret
        elif settings.max_bot_token:
            headers["Authorization"] = settings.max_bot_token
        try:
            with httpx.Client(
                timeout=20.0,
                verify=max_ssl_verify(),
                follow_redirects=True,
            ) as http:
                resp = http.get(url, headers=headers)
            payload["remote_url"] = str(resp.url)
            payload["remote_status"] = resp.status_code
            if resp.status_code < 400:
                data = resp.json()
                payload["remote_discovered"] = data.get("discovered")
                payload["remote_max_channel_chat_id"] = data.get("max_channel_chat_id")
            else:
                payload["remote_error"] = resp.text[:500]
        except Exception as exc:  # noqa: BLE001
            payload["remote_url"] = url
            payload["remote_error"] = str(exc)
    payload["next"] = (
        "If remote_discovered empty: re-add bot as channel admin, "
        "then sfrfr max-channel-info again. "
        "Then set MAX_CHANNEL_CHAT_ID and run sfrfr max-channel-post"
    )
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command("max-channel-review")
def max_channel_review(
    only: str | None = typer.Option(
        None,
        "--only",
        help="id поста(ов) из starter-posts.json через запятую",
    ),
    file: Path | None = typer.Option(
        None,
        "--file",
        help="JSON с постами (по умолчанию starter-posts.json)",
        exists=True,
        dir_okay=False,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Только показать очередь, без отправки",
    ),
    to_channel: bool = typer.Option(
        False,
        "--to-channel",
        help="Дублировать в канал команды (по умолчанию — личка ops-бота)",
    ),
) -> None:
    """Отправить черновик(и) в личку ops-бота на одобрение (не в клиентский канал)."""
    import json
    import time

    from sfrfr.core.config import get_settings
    from sfrfr.integrations.max.channel_review import (
        create_and_send_review,
        review_recipient_user_ids,
    )

    settings = get_settings()
    recipients = review_recipient_user_ids()
    if not recipients and not (
        to_channel and (settings.max_specialists_channel_chat_id or "").strip()
    ):
        if not (settings.max_specialists_channel_chat_id or "").strip():
            raise typer.BadParameter(
                "Задайте STAFF_LOGIN_APPROVER_MAX_USER_IDS "
                "или MAX_SPECIALISTS_CHANNEL_CHAT_ID"
            )
    posts_path = file or Path("scripts/assets/max-channel/starter-posts.json")
    if not posts_path.is_file():
        raise typer.BadParameter(f"Нет файла {posts_path}")
    posts = json.loads(posts_path.read_text(encoding="utf-8"))
    if not isinstance(posts, list) or not posts:
        raise typer.BadParameter("JSON постов пуст")

    only_ids = {part.strip() for part in (only or "").split(",") if part.strip()}
    if only_ids:
        posts = [p for p in posts if isinstance(p, dict) and str(p.get("id") or "") in only_ids]
        if not posts:
            raise typer.BadParameter(f"Не найдены id: {', '.join(sorted(only_ids))}")

    if dry_run:
        typer.echo(
            json.dumps(
                {
                    "mode": "channel" if to_channel else "ops_dm",
                    "user_ids": recipients,
                    "specialists_chat_id": settings.max_specialists_channel_chat_id,
                    "count": len(posts),
                    "ids": [p.get("id") for p in posts if isinstance(p, dict)],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    results: list[dict] = []
    for item in posts:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        source_id = str(item.get("id") or "").strip()
        out = create_and_send_review(
            text=text,
            cta_label=str(item.get("cta_label") or ""),
            cta_kind=str(item.get("cta_kind") or ""),
            cta_url=str(item.get("cta_url") or ""),
            pin=bool(item.get("pin")),
            source_id=source_id,
            draft_id=source_id or None,
            to_channel=to_channel,
        )
        results.append(out)
        time.sleep(0.7)
    typer.echo(json.dumps({"reviewed": results}, ensure_ascii=False, indent=2))


@app.command("max-channel-post")
def max_channel_post(
    text: str = typer.Option(
        "Тест публикации SFRFR: черновик → проверка → API. Не ПДн.",
        "--text",
        "-t",
        help="Текст поста (без ПДн и обещаний перерасчёта)",
    ),
    chat_id: str | None = typer.Option(
        None,
        "--chat-id",
        help="chat_id канала; по умолчанию MAX_CHANNEL_CHAT_ID из .env",
    ),
    review: bool = typer.Option(
        False,
        "--review",
        help="Сначала в личку ops-бота (кнопки Опубликовать / Скопировать / Прислать правку)",
    ),
    to_channel: bool = typer.Option(
        False,
        "--to-channel",
        help="С --review: отправить в канал команды вместо лички ops",
    ),
) -> None:
    """Публикация в канал MAX (или --review в личку ops-бота)."""
    import json

    from sfrfr.core.config import get_settings
    from sfrfr.integrations.max.channel_review import create_and_send_review
    from sfrfr.integrations.max.client import MaxBotClient

    settings = get_settings()
    if review:
        out = create_and_send_review(text=text, to_channel=to_channel)
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))
        return
    target = (chat_id or settings.max_channel_chat_id or "").strip()
    if not target:
        raise typer.BadParameter(
            "Задайте MAX_CHANNEL_CHAT_ID или --chat-id "
            "(см. sfrfr max-channel-info после bot_added)"
        )
    client = MaxBotClient()
    if not client.available:
        raise typer.BadParameter("Задайте MAX_BOT_TOKEN в .env")
    result = client.send_message(text=text, chat_id=target)
    typer.echo(json.dumps({"chat_id": target, "result": result}, ensure_ascii=False, indent=2))


@app.command("max-channel-publish-starter")
def max_channel_publish_starter(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Только показать очередь, без публикации",
    ),
    chat_id: str | None = typer.Option(
        None,
        "--chat-id",
        help="chat_id канала; по умолчанию MAX_CHANNEL_CHAT_ID",
    ),
    only: str | None = typer.Option(
        None,
        "--only",
        help="Опубликовать только пост(ы) по id через запятую (напр. 00-pinned)",
    ),
    review: bool = typer.Option(
        True,
        "--review/--direct",
        help="По умолчанию: в личку ops на одобрение. --direct — сразу в клиентский канал",
    ),
    to_channel: bool = typer.Option(
        False,
        "--to-channel",
        help="С --review: слать в канал команды вместо лички ops",
    ),
) -> None:
    """Черновики из starter-posts.json → review (личка ops) или --direct в клиентский канал."""
    import json
    import time
    from pathlib import Path

    from sfrfr.core.config import get_settings
    from sfrfr.integrations.max.channel_review import (
        create_and_send_review,
        review_recipient_user_ids,
    )
    from sfrfr.integrations.max.client import MaxBotClient, inline_link_keyboard

    settings = get_settings()
    posts_path = Path("scripts/assets/max-channel/starter-posts.json")
    if not posts_path.is_file():
        raise typer.BadParameter(f"Нет файла {posts_path}")
    posts = json.loads(posts_path.read_text(encoding="utf-8"))
    if not isinstance(posts, list) or not posts:
        raise typer.BadParameter("starter-posts.json пуст")

    only_ids = {part.strip() for part in (only or "").split(",") if part.strip()}
    if only_ids:
        posts = [p for p in posts if isinstance(p, dict) and str(p.get("id") or "") in only_ids]
        if not posts:
            raise typer.BadParameter(f"Не найдены id: {', '.join(sorted(only_ids))}")

    if review:
        recipients = review_recipient_user_ids()
        if dry_run:
            typer.echo(
                json.dumps(
                    {
                        "mode": "channel" if to_channel else "ops_dm",
                        "user_ids": recipients,
                        "count": len(posts),
                        "ids": [p.get("id") for p in posts if isinstance(p, dict)],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        if not recipients and not (settings.max_specialists_channel_chat_id or "").strip():
            raise typer.BadParameter(
                "Для --review задайте STAFF_LOGIN_APPROVER_MAX_USER_IDS "
                "или MAX_SPECIALISTS_CHANNEL_CHAT_ID (или --direct)"
            )
        results = []
        for item in posts:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            source_id = str(item.get("id") or "").strip()
            results.append(
                create_and_send_review(
                    text=text,
                    cta_label=str(item.get("cta_label") or ""),
                    cta_kind=str(item.get("cta_kind") or ""),
                    cta_url=str(item.get("cta_url") or ""),
                    pin=bool(item.get("pin")),
                    source_id=source_id,
                    draft_id=source_id or None,
                    to_channel=to_channel,
                )
            )
            time.sleep(0.7)
        typer.echo(
            json.dumps(
                {"mode": "channel" if to_channel else "ops_dm", "reviewed": results},
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    target = (chat_id or settings.max_channel_chat_id or "").strip()
    if not target:
        raise typer.BadParameter("Задайте MAX_CHANNEL_CHAT_ID")

    if dry_run:
        preview = {"mode": "direct", "chat_id": target, "count": len(posts), "posts": posts}
        typer.echo(json.dumps(preview, ensure_ascii=False, indent=2))
        return

    client = MaxBotClient()
    if not client.available:
        raise typer.BadParameter("Задайте MAX_BOT_TOKEN в .env")

    chat_url = (settings.max_chat_url or "").strip()
    published: list[dict[str, object]] = []
    pin_mid: str | None = None

    for item in posts:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        attachments = None
        label = str(item.get("cta_label") or "").strip()
        kind = str(item.get("cta_kind") or "")
        if label and kind == "chat" and chat_url:
            attachments = inline_link_keyboard(label, chat_url)
        elif label and kind == "url":
            url = str(item.get("cta_url") or "").strip()
            if url:
                attachments = inline_link_keyboard(label, url)

        result = client.send_message(text=text, chat_id=target, attachments=attachments)
        mid = None
        msg = result.get("message") if isinstance(result, dict) else None
        if isinstance(msg, dict):
            body = msg.get("body")
            if isinstance(body, dict):
                mid = body.get("mid")
            public_url = msg.get("url")
        else:
            public_url = None
        if item.get("pin") and isinstance(mid, str):
            pin_mid = mid
        published.append(
            {
                "id": item.get("id"),
                "mid": mid,
                "url": public_url,
                "pin": bool(item.get("pin")),
            }
        )
        time.sleep(0.6)  # < 2 msg/sec limit

    pin_result = None
    if pin_mid:
        pin_result = client.pin_message(chat_id=target, message_id=pin_mid, notify=True)

    typer.echo(
        json.dumps(
            {
                "mode": "direct",
                "chat_id": target,
                "published": published,
                "pin": pin_result,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@app.command("staff-list")
def staff_list() -> None:
    """Список сотрудников и ролей (service role)."""
    from sfrfr.db.staff_roles import list_staff_roles

    rows = list_staff_roles()
    if not rows:
        typer.echo("staff_roles пусто. Команда: sfrfr staff-grant --email … --role admin --invite")
        return
    for row in rows:
        typer.echo(f"{row.get('email') or '-'}\t{row['user_id']}\t{row['role']}")


@app.command("staff-grant")
def staff_grant(
    email: str = typer.Option(..., "--email", "-e", help="Рабочий email сотрудника"),
    role: str = typer.Option("admin", "--role", "-r", help="operator|expert|admin"),
    invite: bool = typer.Option(
        False,
        "--invite",
        help="Создать пользователя Auth, если ещё нет (email_confirm=true)",
    ),
) -> None:
    """Выдать staff-роль (обход курицы/яйца: первый admin через CLI)."""
    from sfrfr.db.staff_roles import ensure_user, grant_staff_role, user_id_of
    from sfrfr.security.auth import StaffRole

    try:
        staff_role = StaffRole(role)
    except ValueError as exc:
        raise typer.BadParameter("role: operator|expert|admin") from exc

    try:
        user = ensure_user(email, invite=invite)
    except LookupError as exc:
        raise typer.BadParameter(str(exc)) from exc

    uid = user_id_of(user)
    row = grant_staff_role(uid, staff_role, staff_email=email.strip().lower())
    typer.echo(f"ok\t{email.strip().lower()}\t{uid}\t{row['role']}")


@app.command("ops-health")
def ops_health(
    fail_on_alert: bool = typer.Option(
        True,
        "--fail-on-alert/--no-fail-on-alert",
        help="Exit 1 при failed_alert или неготовности API",
    ),
) -> None:
    """Проверка /health + число дел failed (без ПДн). Для cron/alerting."""
    import json

    from sfrfr.core.config import get_settings
    from sfrfr.ops.health import ops_status_payload

    settings = get_settings()
    payload = ops_status_payload(
        failed_alert_threshold=settings.ops_failed_alert_threshold
    )
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    monitor = payload.get("monitor") or {}
    if fail_on_alert and (
        not monitor.get("api_ready") or monitor.get("failed_alert")
    ):
        raise typer.Exit(code=1)


@app.command("ops-check-remote")
def ops_check_remote(
    base_url: str | None = typer.Option(
        None,
        "--url",
        help="Базовый URL API; по умолчанию PUBLIC_BASE_URL",
    ),
) -> None:
    """HTTP-проверка публичного /health (без секретов)."""
    import json
    import urllib.error
    import urllib.request

    from sfrfr.core.config import get_settings

    settings = get_settings()
    root = (base_url or settings.public_base_url).rstrip("/")
    health_url = f"{root}/health"
    try:
        with urllib.request.urlopen(health_url, timeout=15) as response:
            body = response.read().decode("utf-8")
            status_code = response.status
    except urllib.error.URLError as exc:
        typer.echo(f"FAIL\t{health_url}\t{exc}")
        raise typer.Exit(code=1) from exc
    typer.echo(f"OK\t{status_code}\t{health_url}")
    typer.echo(json.dumps(json.loads(body), ensure_ascii=False, indent=2))
    if status_code >= 400:
        raise typer.Exit(code=1)


@app.command("drive-list")
def drive_list(
    page_size: int = typer.Option(10, "--page-size", "-n", min=1, max=100),
    folder_id: str | None = typer.Option(
        None, "--folder-id", "-f", help="ID папки; иначе GOOGLE_DRIVE_FOLDER_ID"
    ),
) -> None:
    """Список файлов Google Drive через service account (без ПДн)."""
    import json

    from sfrfr.integrations.drive import DriveClient

    result = DriveClient().list_files(page_size=page_size, folder_id=folder_id)
    typer.echo(json.dumps(result, ensure_ascii=False))
    if result.get("skipped"):
        raise typer.Exit(code=0)
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command("drive-mkdir")
def drive_mkdir(
    name: str = typer.Argument(..., help="Имя новой папки"),
    parent_id: str | None = typer.Option(
        None, "--parent", "-p", help="ID родителя; иначе GOOGLE_DRIVE_FOLDER_ID"
    ),
) -> None:
    """Создать папку в Google Drive (idempotent: если есть — вернёт существующую)."""
    import json

    from sfrfr.integrations.drive import DriveClient

    result = DriveClient().create_folder(name, parent_id=parent_id)
    typer.echo(json.dumps(result, ensure_ascii=False))
    if result.get("skipped"):
        raise typer.Exit(code=0)
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command("drive-init-tree")
def drive_init_tree(
    rename_root: bool = typer.Option(
        True,
        "--rename-root/--keep-root-name",
        help="Переименовать корень в «SFRFR — Пенсионные дела»",
    ),
) -> None:
    """Создать рекомендованное дерево папок в GOOGLE_DRIVE_FOLDER_ID."""
    import json

    from sfrfr.integrations.drive import ROOT_FOLDER_NAME, DriveClient

    client = DriveClient()
    if rename_root and client.folder_id:
        renamed = client.rename(client.folder_id, ROOT_FOLDER_NAME)
        if not renamed.get("ok"):
            typer.echo(json.dumps({"rename_root": renamed}, ensure_ascii=False))
            raise typer.Exit(code=1)
    result = client.ensure_workspace_tree()
    # старую папку «Клиенты» не трогаем — структура 02_Кейсы_клиентов создаётся отдельно
    typer.echo(json.dumps(result, ensure_ascii=False))
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command("drive-case-mkdir")
def drive_case_mkdir(
    case_id: str = typer.Argument(..., help="Только case_id, без ФИО/СНИЛС"),
    status: str = typer.Option(
        "active",
        "--status",
        "-s",
        help="active|done|archive → Активные|Завершённые|Архив_по_сроку_хранения",
    ),
) -> None:
    """Создать папку дела в 02_Кейсы_клиентов/... (после согласия на ПДн)."""
    import json

    from sfrfr.integrations.drive import DriveClient

    result = DriveClient().ensure_case_tree(case_id, status=status)
    typer.echo(json.dumps(result, ensure_ascii=False))
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command("calendar-list")
def calendar_list(
    max_results: int = typer.Option(10, "--max", "-n", min=1, max=50),
) -> None:
    """Список ближайших событий Google Calendar (без ПДн)."""
    import json

    from sfrfr.integrations.calendar import CalendarClient

    result = CalendarClient().list_events(max_results=max_results)
    typer.echo(json.dumps(result, ensure_ascii=False))
    if result.get("skipped"):
        raise typer.Exit(code=0)
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command("calendar-create")
def calendar_create(
    case_id: str = typer.Option(..., "--case-id", "-c", help="Только case_id"),
    title: str = typer.Option("consult", "--title", "-t", help="Тип/краткий заголовок без ФИО"),
    start: str = typer.Option(
        ...,
        "--start",
        help="ISO datetime, например 2026-07-25T15:00:00+03:00",
    ),
    duration_minutes: int = typer.Option(60, "--duration", "-d", min=15, max=480),
    task_type: str = typer.Option("consult", "--task", help="consult|deadline|followup"),
    mirror_yandex: bool = typer.Option(
        True,
        "--mirror-yandex/--no-mirror-yandex",
        help="Дублировать событие в Яндекс Календарь",
    ),
) -> None:
    """Создать событие Calendar: summary с case_id, без ФИО/телефона (+ зеркало в Яндекс)."""
    import json
    from datetime import datetime

    from sfrfr.integrations.calendar import CalendarClient
    from sfrfr.integrations.yandex_workspace import create_on_both

    try:
        start_dt = datetime.fromisoformat(start)
    except ValueError as exc:
        raise typer.BadParameter(f"invalid --start: {start}") from exc
    if mirror_yandex:
        result = create_on_both(
            case_id=case_id,
            title=title,
            start=start_dt,
            duration_minutes=duration_minutes,
            task_type=task_type,
        )
    else:
        result = CalendarClient().create_event(
            case_id=case_id,
            title=title,
            start=start_dt,
            duration_minutes=duration_minutes,
            task_type=task_type,
        )
    typer.echo(json.dumps(result, ensure_ascii=False))
    if result.get("skipped"):
        raise typer.Exit(code=0)
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command("gsc-sites")
def gsc_sites() -> None:
    """Список property Google Search Console для SA (ops)."""
    import json

    from sfrfr.integrations.search_console import SearchConsoleClient

    result = SearchConsoleClient().list_sites()
    typer.echo(json.dumps(result, ensure_ascii=False))
    if result.get("skipped"):
        raise typer.Exit(code=0)
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command("yookassa-status")
def yookassa_status(
    expected_provider: str = typer.Option(
        "evotor",
        "--expected-provider",
        help="Ожидаемый fiscalization.provider из /v3/me (канон: evotor → Платформа ОФД)",
    ),
) -> None:
    """Статус магазина ЮKassa + сверка фискализации (без двойных чеков)."""
    import json

    from sfrfr.core.config import get_settings
    from sfrfr.integrations.payments import YooKassaClient, check_fiscalization_alignment

    settings = get_settings()
    me = YooKassaClient().fetch_me()
    align = check_fiscalization_alignment(
        fiscalization_enabled=bool(me.get("fiscalization_enabled")),
        fiscal_provider=str(me["fiscal_provider"]) if me.get("fiscal_provider") else None,
        send_receipt=bool(settings.yookassa_send_receipt),
        expected_provider=(expected_provider or "").strip().lower() or "evotor",
    )
    out = {
        "me": {k: me.get(k) for k in (
            "ok", "skipped", "status_code", "account_id", "status", "test",
            "fiscalization_enabled", "fiscal_provider", "payment_methods", "error", "reason",
        ) if k in me},
        "alignment": align,
        "send_receipt_env": bool(settings.yookassa_send_receipt),
    }
    typer.echo(json.dumps(out, ensure_ascii=False))
    if me.get("skipped"):
        raise typer.Exit(code=0)
    if not me.get("ok") or not align.get("ok"):
        raise typer.Exit(code=1)


@app.command("amocrm-ensure-fields")
def amocrm_ensure_fields() -> None:
    """Создать/обновить custom fields сделки: русские названия, ARCHIVE_*, скрыть черновики."""
    import json

    from sfrfr.integrations.amocrm import ensure_amocrm_lead_fields

    result = ensure_amocrm_lead_fields()
    typer.echo(json.dumps(result, ensure_ascii=False))
    if result.get("skipped"):
        raise typer.Exit(code=0)
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command("diagnosis-survey-due-tick")
def diagnosis_survey_due_tick() -> None:
    """scheduled surveys → draft (без автоотправки)."""
    from sfrfr.services.diagnosis_survey import DiagnosisSurveyService

    stats = DiagnosisSurveyService().run_due_tick()
    typer.echo(stats)


@app.command("notification-smtp-retry")
def notification_smtp_retry() -> None:
    """Retry failed Yandex SMTP notification_jobs (backoff)."""
    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.db.diagnosis_delivery_repository import DiagnosisDeliveryRepository
    from sfrfr.services.diagnosis_delivery import DiagnosisDeliveryService

    failed = DiagnosisDeliveryRepository().list_failed_jobs(limit=30)
    cases = CaseRepository()
    email_by_case: dict[str, str] = {}
    for job in failed:
        cid = str(job.get("case_id") or "")
        if not cid or cid in email_by_case:
            continue
        case = cases.get_case_row(cid)
        if not case or not case.get("client_id"):
            continue
        crow = (
            cases.client.table("clients")
            .select("email")
            .eq("id", case["client_id"])
            .limit(1)
            .execute()
        )
        rows = crow.data or []
        email = str((rows[0] if rows else {}).get("email") or "").strip()
        if email:
            email_by_case[cid] = email
    stats = DiagnosisDeliveryService().retry_smtp_failures(email_by_case=email_by_case)
    typer.echo(stats)


@app.command("amocrm-sync")
def amocrm_sync(
    case_id: str = typer.Option(..., "--case-id", "-c", help="UUID дела"),
) -> None:
    """Отправить минимум данных дела в amoCRM."""
    import json

    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.integrations.amocrm.sync import persist_crm_external_id, push_case_to_amocrm
    from sfrfr.security.auth import Principal, StaffRole

    repo = CaseRepository()
    principal = Principal(user_id="cli", role=StaffRole.ADMIN, email=None)
    case = repo.require_case(principal, case_id)
    result = push_case_to_amocrm(case, task="cli_sync")
    lead_id = result.get("lead_id")
    if lead_id and result.get("ok"):
        persist_crm_external_id(case_id, str(lead_id))
    typer.echo(json.dumps(result, ensure_ascii=False))
    if result.get("skipped"):
        raise typer.Exit(code=0)
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command("yandex-workspace-ping")
def yandex_workspace_ping() -> None:
    """Проверить OAuth-токен Яндекс Workspace (ТЗ-14) + IMAP при включённом флаге."""
    import json

    from sfrfr.core.config import get_settings
    from sfrfr.integrations.yandex_workspace import imap_ping, ping

    result = ping()
    if get_settings().yandex_mail_imap_enabled:
        result["imap"] = imap_ping()
    typer.echo(json.dumps(result, ensure_ascii=False))
    if result.get("skipped"):
        raise typer.Exit(code=0)
    if not result.get("ok"):
        raise typer.Exit(code=1)
    imap = result.get("imap") or {}
    if imap and not imap.get("ok") and not imap.get("skipped"):
        raise typer.Exit(code=1)


@app.command("yandex-telemost-create")
def yandex_telemost_create(
    case_id: str = typer.Option(..., "--case-id", "-c", help="UUID дела"),
) -> None:
    """Создать встречу Телемост и сохранить meeting_url на деле."""
    import json

    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.db.session import get_supabase_client
    from sfrfr.integrations.yandex_workspace import create_conference
    from sfrfr.security.auth import Principal, StaffRole

    repo = CaseRepository()
    principal = Principal(user_id="cli", role=StaffRole.ADMIN, email=None)
    repo.require_case(principal, case_id)
    result = create_conference(title_note=f"case:{case_id}")
    if result.get("ok") and result.get("join_url"):
        try:
            get_supabase_client().table("cases").update(
                {"meeting_url": str(result["join_url"])}
            ).eq("id", case_id).execute()
            repo.audit(case_id, None, f"yandex_telemost_create:{result.get('conference_id')}")
        except Exception as exc:  # noqa: BLE001
            result["persist_error"] = type(exc).__name__
            result["persist_detail"] = str(exc)[:200]
    typer.echo(json.dumps(result, ensure_ascii=False))
    if result.get("skipped"):
        raise typer.Exit(code=0)
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command("yandex-calendar-create")
def yandex_calendar_create(
    case_id: str = typer.Option(..., "--case-id", "-c"),
    start: str = typer.Option(..., "--start", help="ISO datetime"),
    title: str = typer.Option("consult", "--title", "-t"),
    duration_minutes: int = typer.Option(30, "--duration", "-d", min=15, max=480),
) -> None:
    """Создать событие только в Яндекс Календаре (CalDAV)."""
    import json
    from datetime import datetime

    from sfrfr.integrations.yandex_workspace import create_event

    try:
        start_dt = datetime.fromisoformat(start)
    except ValueError as exc:
        raise typer.BadParameter(f"invalid --start: {start}") from exc
    result = create_event(
        case_id=case_id,
        summary=title,
        starts_at=start_dt,
        duration_minutes=duration_minutes,
    )
    typer.echo(json.dumps(result, ensure_ascii=False))
    if result.get("skipped"):
        raise typer.Exit(code=0)
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command("calendar-mirror-yandex")
def calendar_mirror_yandex(
    max_results: int = typer.Option(25, "--max", "-n", min=1, max=50),
) -> None:
    """Скопировать ближайшие события Google Calendar → Яндекс."""
    import json

    from sfrfr.integrations.yandex_workspace import mirror_google_to_yandex

    result = mirror_google_to_yandex(max_results=max_results)
    typer.echo(json.dumps(result, ensure_ascii=False))
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command("yandex-disk-status")
def yandex_disk_status() -> None:
    """Статус Яндекс Диска + папка SFRFR-ops."""
    import json

    from sfrfr.integrations.yandex_workspace import disk_status, ensure_ops_folder, list_ops

    status = disk_status()
    if status.get("ok"):
        folder = ensure_ops_folder()
        listed = list_ops()
        status["ops_folder_ensure"] = folder
        status["ops_list"] = {
            "ok": listed.get("ok"),
            "count": listed.get("count"),
            "items": listed.get("items"),
        }
    typer.echo(json.dumps(status, ensure_ascii=False))
    if status.get("skipped"):
        raise typer.Exit(code=0)
    if not status.get("ok"):
        raise typer.Exit(code=1)


@app.command("yandex-mail-send")
def yandex_mail_send(
    to: str = typer.Option(..., "--to", help="Email получателя"),
    template: str = typer.Option("request_docs", "--template", "-t"),
    case_id: str | None = typer.Option(None, "--case-id", "-c"),
    subject: str | None = typer.Option(None, "--subject"),
    body: str | None = typer.Option(None, "--body"),
) -> None:
    """Отправить письмо с ящика Workspace (шаблоны request_docs|reminder|custom)."""
    import json

    from sfrfr.integrations.yandex_workspace import send_mail

    result = send_mail(
        to=to,
        template=template,
        case_id=case_id,
        subject=subject,
        body=body,
    )
    if case_id and result.get("ok"):
        try:
            from sfrfr.db.case_repository import CaseRepository

            CaseRepository().audit(case_id, None, f"yandex_mail_send:{template}")
        except Exception:  # noqa: BLE001
            pass
    typer.echo(json.dumps(result, ensure_ascii=False))
    if result.get("skipped"):
        raise typer.Exit(code=0)
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command("yandex-mail-imap-ping")
def yandex_mail_imap_ping() -> None:
    """Проверить IMAP XOAUTH2 для proverkastaza@yandex.ru."""
    import json

    from sfrfr.integrations.yandex_workspace import imap_ping

    result = imap_ping()
    typer.echo(json.dumps(result, ensure_ascii=False))
    if result.get("skipped"):
        raise typer.Exit(code=0)
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command("yandex-mail-list")
def yandex_mail_list(
    limit: int = typer.Option(10, "--limit", "-n", min=1, max=100),
    unseen: bool = typer.Option(False, "--unseen", help="Только непрочитанные"),
) -> None:
    """Список входящих (метаданные, без тела)."""
    import json

    from sfrfr.integrations.yandex_workspace import list_inbox

    result = list_inbox(limit=limit, unseen_only=unseen)
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("skipped"):
        raise typer.Exit(code=0)
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command("yandex-mail-fetch")
def yandex_mail_fetch(
    uid: str = typer.Argument(..., help="IMAP UID письма"),
    body: bool = typer.Option(False, "--body", help="Включить текст (с маскированием ПДн)"),
) -> None:
    """Получить одно письмо по UID."""
    import json

    from sfrfr.integrations.yandex_workspace import fetch_message

    result = fetch_message(uid, include_body=body, redact_body=True)
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("skipped"):
        raise typer.Exit(code=0)
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command("site-reviews-list")
def site_reviews_list(
    status: str = typer.Option("pending", "--status", "-s", help="pending|published|all"),
) -> None:
    """Очередь цитат для главной (без ПДн в выводе сверх текста цитаты)."""
    import json

    from sfrfr.core import site_reviews as sr

    if status == "published":
        items = sr.list_published(limit=50)
    elif status == "all":
        with sr._STORE_LOCK:  # noqa: SLF001
            items = (sr._load().get("items") or [])[:100]  # noqa: SLF001
    else:
        items = sr.list_pending(limit=50)
    payload = {"ok": True, "count": len(items), "items": items}
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command("site-reviews-set")
def site_reviews_set(
    item_id: str = typer.Argument(..., help="UUID цитаты"),
    status: str = typer.Option(..., "--status", "-s", help="published|rejected|pending"),
) -> None:
    """Опубликовать / отклонить цитату (не трогает рейтинг Яндекса)."""
    import json

    from sfrfr.core.site_reviews import set_status

    result = set_status(item_id, status)
    typer.echo(json.dumps(result, ensure_ascii=False))
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command("max-channel-daily-tick")
def max_channel_daily_tick(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Показать следующий id без отправки",
    ),
    mark_only: str | None = typer.Option(
        None,
        "--mark-sent",
        help="Только отметить id как отправленный (без публикации), напр. после ручного review",
    ),
) -> None:
    """Ежедневный полуавто: один пост из daily-queue → личка ops (кнопка Опубликовать).

    Не публикует сразу в клиентский канал. Cron/systemd: раз в сутки.
    """
    import json

    from sfrfr.integrations.max.channel_daily import (
        load_post_by_id,
        mark_sent,
        peek_daily,
    )
    from sfrfr.integrations.max.channel_review import create_and_send_review

    if mark_only:
        state = mark_sent(mark_only.strip())
        typer.echo(
            json.dumps(
                {"ok": True, "marked": mark_only.strip(), "state": state},
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    peek = peek_daily()
    next_id = peek.get("next_id")
    if dry_run or not next_id:
        typer.echo(json.dumps(peek, ensure_ascii=False, indent=2))
        if not next_id:
            raise typer.Exit(code=0)
        return

    post = load_post_by_id(str(next_id))
    text = str(post.get("text") or "").strip()
    if not text:
        raise typer.BadParameter(f"пустой text у {next_id}")

    out = create_and_send_review(
        text=text,
        cta_label=str(post.get("cta_label") or ""),
        cta_kind=str(post.get("cta_kind") or ""),
        cta_url=str(post.get("cta_url") or ""),
        pin=bool(post.get("pin")),
        source_id=str(next_id),
        draft_id=str(next_id),
        to_channel=False,
    )
    state = mark_sent(str(next_id))
    typer.echo(
        json.dumps(
            {"ok": True, "sent_id": next_id, "review": out, "state": state},
            ensure_ascii=False,
            indent=2,
        )
    )


@app.command("finance-due-tick")
def finance_due_tick() -> None:
    """Ежедневная проверка сроков оплаты: задача сотруднику и черновик напоминания.

    Не отправляет сообщения клиенту в MAX и не создаёт платежи ЮKassa.
    """
    import json

    from sfrfr.db.case_repository import CaseRepository
    from sfrfr.services.finance_automation import run_due_tick

    stats = run_due_tick(CaseRepository())
    typer.echo(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    app()
