"""Интеграция с мессенджером MAX."""

from sfrfr.integrations.max.client import MaxBotClient
from sfrfr.integrations.max.handler import MaxHandleResult, handle_max_update

__all__ = ["MaxBotClient", "MaxHandleResult", "handle_max_update"]
