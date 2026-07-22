"""B2C финансовые и клиентские статусы дела."""

from __future__ import annotations

from enum import StrEnum


class B2CStatus(StrEnum):
    """Статусы монетизации и клиентского сопровождения (параллельно CaseStatus)."""

    LEAD = "lead"
    CONSENT_ACCEPTED = "consent_accepted"
    DIAGNOSTIC_PAID = "diagnostic_paid"
    CONTRACT_ACCEPTED = "contract_accepted"
    SERVICE_PAID = "service_paid"
    PACKAGE_DELIVERED = "package_delivered"
    AWAITING_CLIENT_SUBMISSION = "awaiting_client_submission"
    RESULT_PENDING = "result_pending"
    RESULT_CONFIRMED = "result_confirmed"
    SUCCESS_FEE_DUE = "success_fee_due"
    SUCCESS_FEE_PAID = "success_fee_paid"
    CLIENT_SILENT_ESCALATION = "client_silent_escalation"
    CLOSED = "closed"
