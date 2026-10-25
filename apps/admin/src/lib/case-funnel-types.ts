/** Типы воронки дела (13 UI-ступеней). Заменяет прежнюю типизацию. */

export const FUNNEL_STAGE_IDS = [
  "contact_consents",
  "documents",
  "precheck_summary",
  "analysis_payment",
  "full_analysis",
  "appeals_consent",
  "appeals_payment",
  "appeals_documents",
  "submission",
  "follow_up",
  "response_review",
  "escalation_package",
  "closure",
] as const;

export type FunnelStageId = (typeof FUNNEL_STAGE_IDS)[number];

/** @deprecated alias */
export const STAGE_IDS = FUNNEL_STAGE_IDS;
/** @deprecated alias */
export const FUNNEL_STAGE_ORDER = FUNNEL_STAGE_IDS;

export type StageStatus =
  | "not_started"
  | "in_progress"
  | "waiting"
  | "needs_action"
  | "done"
  | "blocked"
  | "not_required"
  | "unknown";

/** Визуальная оболочка StageShell (не путать с StageStatus). */
export type FunnelStageState =
  | "done"
  | "current"
  | "waiting"
  | "blocked"
  | "overdue"
  | "todo";

export type StageActionId =
  | "edit_contacts"
  | "request_consents"
  | "upload_documents"
  | "run_precheck"
  | "view_precheck"
  | "send_summary"
  | "open_analysis_order"
  | "prepare_analysis"
  | "deliver_analysis"
  | "request_appeals_consent"
  | "open_appeals_order"
  | "prepare_appeals"
  | "deliver_appeals"
  | "record_submission"
  | "request_submission_help"
  | "schedule_call"
  | "record_follow_up"
  | "review_response"
  | "open_escalation"
  | "review_closure"
  | "view_history";

/** @deprecated имя — то же, что StageActionId */
export type FunnelAction = StageActionId;

export type StageAction = Readonly<{
  id: StageActionId;
  label: string;
  enabled: boolean;
  disabledReason?: string;
}>;

export type StageView = Readonly<{
  id: FunnelStageId;
  title: string;
  status: StageStatus;
  summary: string;
  blockers: readonly string[];
  actions: readonly StageAction[];
  dueAt?: string;
}>;

export type FunnelView = Readonly<{
  stages: readonly StageView[];
  currentStageId: FunnelStageId | null;
}>;

export const STAGE_TITLES = {
  contact_consents: "Контакт и согласия",
  documents: "Документы",
  precheck_summary: "Первичная проверка и резюме",
  analysis_payment: "Оплата подробного анализа",
  full_analysis: "Подробный анализ",
  appeals_consent: "Согласование обращений",
  appeals_payment: "Оплата подготовки обращений",
  appeals_documents: "Обращения и передача клиенту",
  submission: "Подача и помощь специалиста",
  follow_up: "Контроль рассмотрения",
  response_review: "Ответ СФР и дальнейшие действия",
  escalation_package: "Дополнительные обращения",
  closure: "Итог и завершение дела",
} as const satisfies Record<FunnelStageId, string>;

export type Loaded<T> =
  | Readonly<{ state: "loaded"; value: T }>
  | Readonly<{ state: "unavailable"; reason: string }>;

export type ServiceOrderFacts = Readonly<{
  orderId: string | null;
  status: "not_ordered" | "pending" | "paid" | "canceled" | "refunded" | "unknown";
  amountRub: number | null;
  payUrl: string | null;
  entitlement: "granted" | "none" | "unknown";
}>;

export type OutgoingDocumentFacts = Readonly<{
  id: string;
  versionId: string;
  title: string;
  recipient: string;
  formats: readonly ("docx" | "pdf")[];
  review: "draft" | "reviewed";
  clientApproval: "not_requested" | "pending" | "approved";
  delivery: "not_sent" | "queued" | "confirmed" | "unknown";
}>;

export type SubmissionFacts = Readonly<{
  status: "not_started" | "awaiting_client" | "help_requested" | "confirmed";
  recipient: string | null;
  submittedAt: string | null;
  referenceNumber: string | null;
}>;

export type FollowUpFacts = Readonly<{
  status: "inactive" | "active" | "paused" | "completed";
  nextCheckAt: string | null;
  callRequired: boolean;
  openCallTaskId: string | null;
}>;

export type ResponseFacts = Readonly<{
  documentId: string;
  status: "received" | "reviewing" | "reviewed";
  kind: "request_documents" | "positive" | "partial" | "refusal" | "other" | "undetermined";
  dueAt: string | null;
  nextStep: string | null;
}>;

export type EscalationFacts = Readonly<{
  decision: "undetermined" | "not_needed" | "recommended";
  consent: "not_requested" | "pending" | "accepted" | "declined";
  order: ServiceOrderFacts;
  documents: readonly OutgoingDocumentFacts[];
}>;

export type ClosureFacts = Readonly<{
  status: "open" | "review_required" | "closed";
  reason: string | null;
  closedAt: string | null;
  chronologyReady: boolean;
}>;

export type LaterStageFacts = Readonly<{
  appealsOrder: Loaded<ServiceOrderFacts>;
  appealsDocuments: Loaded<readonly OutgoingDocumentFacts[]>;
  submission: Loaded<SubmissionFacts>;
  followUp: Loaded<FollowUpFacts>;
  responses: Loaded<readonly ResponseFacts[]>;
  escalation: Loaded<EscalationFacts>;
  closure: Loaded<ClosureFacts>;
}>;

export type LegacyStageId =
  | "contact"
  | "documents"
  | "diagnostics"
  | "plan"
  | "payment"
  | "result"
  | "knowledge";

/** Навигационная совместимость; payment намеренно null (три коммерческих этапа). */
export const LEGACY_TO_NEW = {
  contact: "contact_consents",
  documents: "documents",
  diagnostics: "precheck_summary",
  plan: "full_analysis",
  payment: null,
  result: "response_review",
  knowledge: "closure",
} as const satisfies Record<LegacyStageId, FunnelStageId | null>;

export function loaded<T>(value: T): Loaded<T> {
  return { state: "loaded", value };
}

export function unavailable<T>(reason: string): Loaded<T> {
  return { state: "unavailable", reason };
}

export function defaultLaterStageFactsUnavailable(
  reason = "Источник данных этапа ещё не подключён к API",
): LaterStageFacts {
  return {
    appealsOrder: unavailable(reason),
    appealsDocuments: unavailable(reason),
    submission: unavailable(reason),
    followUp: unavailable(reason),
    responses: unavailable(reason),
    escalation: unavailable(reason),
    closure: unavailable(reason),
  };
}
