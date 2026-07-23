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
        f"находок={len(record.ctx.findings)}\tчерновик={'да' if record.ctx.draft else 'нет'}"
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
        f"ошибка={ctx.error or '-'}"
    )


@app.command("max-subscribe")
def max_subscribe(
    url: str | None = typer.Option(
        None,
        "--url",
        help="HTTPS webhook; по умолчанию PUBLIC_BASE_URL + /api/integrations/max/webhook",
    ),
) -> None:
    """Зарегистрировать webhook бота MAX."""
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


if __name__ == "__main__":
    app()
