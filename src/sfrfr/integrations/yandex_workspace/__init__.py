"""Интеграция Яндекс Workspace (ТЗ-14): почта, Телемост, календарь, Диск."""

from sfrfr.integrations.yandex_workspace.calendar_mirror import (
    create_on_both,
    mirror_google_to_yandex,
)
from sfrfr.integrations.yandex_workspace.calendar_yandex import create_event
from sfrfr.integrations.yandex_workspace.case_cleanup import (
    audit_case_folders,
    cleanup_duplicate_uuid_folders,
    normalize_legacy_folders,
)
from sfrfr.integrations.yandex_workspace.case_mirror import (
    export_case_chat_to_disk_safe,
    mirror_case_document_safe,
)
from sfrfr.integrations.yandex_workspace.disk import (
    CASE_SUBFOLDERS,
    CASES_FOLDER,
    OPS_MARKETING_MAX_FUNNEL,
    delete_case_path,
    disk_status,
    ensure_case_folder,
    ensure_case_layout,
    ensure_cases_folder,
    ensure_ops_folder,
    ensure_ops_path,
    list_case_dir,
    list_ops,
    mirror_case_document,
    move_case_path,
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
    "ensure_case_layout",
    "CASES_FOLDER",
    "CASE_SUBFOLDERS",
    "OPS_MARKETING_MAX_FUNNEL",
    "list_ops",
    "upload_ops_file",
    "upload_case_file",
    "mirror_case_document",
    "mirror_case_document_safe",
    "export_case_chat_to_disk_safe",
    "list_case_dir",
    "move_case_path",
    "delete_case_path",
    "audit_case_folders",
    "cleanup_duplicate_uuid_folders",
    "normalize_legacy_folders",
]
