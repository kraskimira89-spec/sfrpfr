"""Prometheus-метрики конвейера чата и bot_reply (без ПДн в labels)."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

CHAT_MESSAGE_RECEIVED = Counter(
    "chat_message_received_total",
    "Принято клиентских сообщений",
    ["channel"],
)
BOT_JOB_QUEUED = Counter("bot_job_queued_total", "Поставлено задач bot_reply")
BOT_JOB_COMPLETED = Counter("bot_job_completed_total", "Успешно завершённые bot_reply")
BOT_JOB_FAILED = Counter(
    "bot_job_failed_total",
    "Проваленные bot_reply",
    ["error_category"],
)
BOT_REPLY_LATENCY = Histogram(
    "bot_reply_latency_seconds",
    "Время от постановки job до completed/failed",
    buckets=(1.0, 3.0, 10.0, 25.0, 45.0, 60.0, 120.0),
)
BOT_QUEUE_DEPTH = Gauge("bot_queue_depth", "Задач bot_reply в queued/retrying/processing")
LLM_REQUEST_TOTAL = Counter("llm_request_total", "Запросы LLM для чата", ["outcome"])
MAX_WEBHOOK_TOTAL = Counter("max_webhook_total", "Входящие webhook MAX")
MAX_WEBHOOK_SIGNATURE_FAILED = Counter(
    "max_webhook_signature_failed_total",
    "Отклонённые webhook MAX (подпись)",
)


def metrics_payload() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST


def refresh_queue_depth(*, depth: int) -> None:
    BOT_QUEUE_DEPTH.set(max(0, depth))
