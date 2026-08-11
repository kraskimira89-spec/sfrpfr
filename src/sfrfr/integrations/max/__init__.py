"""Интеграция с мессенджером MAX."""

from sfrfr.integrations.max.client import MaxBotClient
from sfrfr.integrations.max.handler import MaxHandleResult, handle_max_update
from sfrfr.integrations.max.ops_bot import get_ops_bot, handle_ops_update

__all__ = [
    "MaxBotClient",
    "MaxHandleResult",
    "get_ops_bot",
    "handle_max_update",
    "handle_ops_update",
]
