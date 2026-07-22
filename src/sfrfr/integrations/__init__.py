"""Интеграции: MAX, шаблоны заявлений (СФР/МФЦ)."""

from sfrfr.integrations.max import MaxBotClient, handle_max_update

__all__ = ["MaxBotClient", "handle_max_update"]
