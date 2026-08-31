"""Интеграция Яндекс Workspace (ТЗ-14): почта, Телемост, календарь, Диск."""

from sfrfr.integrations.yandex_workspace.calendar_mirror import (
    create_on_both,
    mirror_google_to_yandex,
)
from sfrfr.integrations.yandex_workspace.calendar_yandex import create_event
from sfrfr.integrations.yandex_workspace.case_mirror import mirror_case_document_safe
from sfrfr.integrations.yandex_workspace.disk import (
    CASES_FOLDER,
    OPS_MARKETING_MAX_FUNNEL,
    disk_status,
    ensure_case_folder,
    ensure_cases_folder,
    ensure_ops_folder,
    ensure_ops_path,
    list_ops,
    mirror_case_document,
    upload_case_file,
    upload_ops_file,
)
from sfrfr.integrations.yandex_workspace.mail import send_mail
from sfrfr.integrations.yandex_workspace.mail_imap import fetch_message, imap_ping, list_inbox
from sfrfr.integrations.yandex_workspace.oauth import load_workspace_secrets, ping, token_available
from sfrfr.integrations.yandex_workspace.telemost import create_conference

__all__ = [
    "load_workspace_secrets",
    "token_available",
    "ping",
    "create_conference",
    "send_mail",
    "imap_ping",
    "list_inbox",
    "fetch_message",
    "create_event",
    "create_on_both",
    "mirror_google_to_yandex",
    "disk_status",
    "ensure_ops_folder",
    "ensure_ops_path",
    "ensure_cases_folder",
    "ensure_case_folder",
    "CASES_FOLDER",
    "OPS_MARKETING_MAX_FUNNEL",
    "list_ops",
    "upload_ops_file",
    "upload_case_file",
    "mirror_case_document",
    "mirror_case_document_safe",
]
