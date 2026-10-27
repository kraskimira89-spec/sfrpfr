/** Единые типы 13 ступеней воронки дела. */

export const STAGE_IDS = [
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

export type StageId = (typeof STAGE_IDS)[number];

/** @deprecated alias */
export type FunnelStageId = StageId;
/** @deprecated alias */
export const FUNNEL_STAGE_IDS = STAGE_IDS;
/** @deprecated alias */
export const FUNNEL_STAGE_ORDER = STAGE_IDS;

export type StageStatus =
  | "unknown"
  | "not_started"
  | "blocked"
  | "waiting"
  | "in_progress"
  | "needs_action"
  | "done"
  | "not_required";

/** Визуальная оболочка StageShell (не путать с StageStatus). */
export type FunnelStageState =
  | "done"
  | "current"
  | "waiting"
  | "blocked"
  | "overdue"
  | "todo";

export const STAGE_TITLES = {
  contact_consents: "Контакт и согласия",
  documents: "Документы",
  precheck_summary: "Первичная проверка и резюме",
  analysis_payment: "Оплата подробного анализа",
  full_analysis: "Подробный анализ",
  appeals_consent: "Согласование первичных обращений",
  appeals_payment: "Оплата первичных обращений",
  appeals_documents: "Первичные обращения и передача клиенту",
  submission: "Подача и помощь специалиста",
  follow_up: "Контроль рассмотрения",
  response_review: "Ответ СФР и дальнейшие действия",
  escalation_package: "Обращения по запросам / отказам СФР",
  closure: "Итог и завершение дела",
} as const satisfies Record<StageId, string>;

export type ActionId =
  | "edit_contacts"
  | "upload_documents"
  | "run_precheck"
  | "view_precheck"
  | "send_summary"
  | "open_analysis_order"
  | "open_analysis"
  | "request_appeals_consent"
  | "open_appeals_order"
  | "open_appeals"
  | "record_submission"
  | "schedule_call"
  | "record_follow_up"
  | "review_response"
  | "open_escalation"
  | "review_closure";

export type StageView = Readonly<{
  id: StageId;
  title: string;
  status: StageStatus;
  summary: string;
  blockers: readonly string[];
  action?: ActionId;
  dueAt?: string;
}>;

export type FunnelView = Readonly<{
  stages: readonly StageView[];
  /** Где дело в маршруте 1→13 (первый незавершённый обязательный этап). */
  currentStageId: StageId | null;
  /**
   * Срочная задача сотрудника (ответ СФР, устаревшая проверка и т.п.).
   * Не подменяет currentStageId: можно подсветить отдельно.
   */
  priorityStageId?: StageId | null;
}>;

export type Decision =
  | "unknown"
  | "not_requested"
  | "pending"
  | "accepted"
  | "declined";

export type Need = "unknown" | "not_needed" | "recommended";

export type OrderFacts = Readonly<{
  state: "unknown" | "not_ordered" | "pending" | "paid" | "canceled" | "refunded";
  amountRub?: number;
  entitlement: "unknown" | "none" | "granted";
}>;

export type WorkFacts = Readonly<{
  state: "unknown" | "not_started" | "working" | "ready" | "delivered";
  /** Весь согласованный пакет проверен и готов к выдаче — не один файл и не оплата. */
  releaseReady: "unknown" | "no" | "yes";
}>;

export type FunnelFacts = Readonly<{
  contact: "unknown" | "incomplete" | "complete";
  documents: "unknown" | "missing" | "processing" | "needs_action" | "ready";

  precheck: {
    state: "unknown" | "not_started" | "queued" | "running" | "failed" | "completed";
    stale: boolean;
    outcome: "unknown" | "clear" | "discrepancies" | "clarify";
    summaryDelivery: "unknown" | "not_sent" | "confirmed";
  };

  analysis: {
    need: Need;
    order: OrderFacts;
    work: WorkFacts;
  };

  appeals: {
    need: Need;
    consent: Decision;
    order: OrderFacts;
    work: WorkFacts;
  };

  submission:
    | "unknown"
    | "not_started"
    | "awaiting_client"
    | "help_requested"
    | "confirmed";

  /** Фактическая дата подачи из отчёта (YYYY-MM-DD); для ступени 10. */
  submittedOn?: string;
  /** Сотрудник отдельно проверил подтверждающий документ приёма. */
  receiptVerified: boolean;

  followUp: {
    state: "unknown" | "inactive" | "active" | "paused" | "completed";
    callRequired: boolean;
    dueAt?: string;
    /** Копия submittedOn для handoff ступени 10 (контроль даты — вручную). */
    submittedOn?: string;
  };

  response: "unknown" | "none" | "received" | "reviewing" | "reviewed";

  escalation: {
    need: Need;
    consent: Decision;
    order: OrderFacts;
    work: WorkFacts;
  };

  closure: {
    state: "unknown" | "open" | "review_required" | "closed";
    reason?: string;
  };

  preferredStageId?: StageId;
  allowedActions: readonly ActionId[];
}>;

export type LegacyStageId =
  | "contact"
  | "documents"
  | "diagnostics"
  | "plan"
  | "payment"
  | "result"
  | "knowledge";

export const LEGACY_TO_NEW = {
  contact: "contact_consents",
  documents: "documents",
  diagnostics: "precheck_summary",
  plan: "full_analysis",
  payment: null,
  result: "response_review",
  knowledge: "closure",
} as const satisfies Record<LegacyStageId, StageId | null>;
