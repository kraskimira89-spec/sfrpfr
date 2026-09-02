"""Yandex Cloud Postbox: исходящая почта + события доставки."""

from sfrfr.integrations.yandex_postbox.send import postbox_configured, send_email_postbox

__all__ = ["postbox_configured", "send_email_postbox"]
