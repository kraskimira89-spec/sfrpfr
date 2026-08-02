"""Интеграции: MAX, amoCRM, Yandex Workspace, Sheets, Drive, Calendar, reCAPTCHA, ЮKassa."""

from sfrfr.integrations.amocrm import AmoCrmClient, sync_case_to_amocrm
from sfrfr.integrations.calendar import CalendarClient
from sfrfr.integrations.drive import DriveClient
from sfrfr.integrations.max import MaxBotClient, handle_max_update
from sfrfr.integrations.payments import YooKassaClient, parse_yookassa_event
from sfrfr.integrations.recaptcha import RecaptchaVerifier
from sfrfr.integrations.smartcaptcha import SmartCaptchaVerifier
from sfrfr.integrations.search_console import SearchConsoleClient
from sfrfr.integrations.sheets import SheetsExporter, sanitize_rows
from sfrfr.integrations.yandex_workspace import create_conference, ping, send_mail

__all__ = [
    "MaxBotClient",
    "handle_max_update",
    "AmoCrmClient",
    "sync_case_to_amocrm",
    "SheetsExporter",
    "sanitize_rows",
    "DriveClient",
    "CalendarClient",
    "RecaptchaVerifier",
    "SmartCaptchaVerifier",
    "SearchConsoleClient",
    "YooKassaClient",
    "parse_yookassa_event",
    "ping",
    "create_conference",
    "send_mail",
]
