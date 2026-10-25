/** Воронка карточки дела: 13 UI-ступеней (адаптер фактов, не новые backend-статусы). */

export type FunnelStageId =
  | "contact_consents"
  | "documents"
  | "precheck_summary"
  | "analysis_payment"
  | "full_analysis"
  | "appeals_consent"
  | "appeals_payment"
  | "appeals_documents"
  | "submission"
  | "follow_up"
  | "response_review"
  | "escalation_package"
  | "closure";

export type FunnelStageState = "done" | "current" | "waiting" | "blocked" | "overdue" | "todo";

export type FunnelStageCapability = "live" | "partial" | "not_wired" | "optional";

export type FunnelStage = {
  id: FunnelStageId;
  label: string;
  state: FunnelStageState;
  reason: string;
  canAct: boolean;
  shortSummary: string;
  capability: FunnelStageCapability;
};

export const FUNNEL_STAGE_ORDER: FunnelStageId[] = [
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
];

const LABELS: Record<FunnelStageId, string> = {
  contact_consents: "Контакты и согласия",
  documents: "Документы",
  precheck_summary: "Первичная проверка и резюме",
  analysis_payment: "Оплата подробного анализа",
  full_analysis: "Подробный анализ",
  appeals_consent: "Согласование подготовки обращений",
  appeals_payment: "Оплата подготовки обращений",
  appeals_documents: "Обращения и передача клиенту",
  submission: "Подача и помощь специалиста",
  follow_up: "Контроль рассмотрения",
  response_review: "Ответ СФР и дальнейшие действия",
  escalation_package: "Дополнительные обращения — при необходимости",
  closure: "Итог и завершение дела",
};

function checklistDone(
  items: { title?: string; status?: string; item_type?: string }[],
  needle: RegExp,
): boolean {
  const matched = items.filter((i) => needle.test(String(i.title || "")));
  if (matched.length === 0) return false;
  return matched.every((i) => i.status === "done");
}

function hasDocType(
  docs: { doc_type?: string | null; storage_path?: string }[],
  needles: string[],
): boolean {
  return docs.some((d) => {
    const t = `${d.doc_type || ""} ${d.storage_path || ""}`.toLowerCase();
    return needles.some((n) => t.includes(n));
  });
}

function isOverdue(nextActionAt?: string | null): boolean {
  if (!nextActionAt) return false;
  const due = new Date(nextActionAt);
  if (Number.isNaN(due.getTime())) return false;
  return due.getTime() < Date.now();
}

function orderStatusPaid(status: string): boolean {
  return ["paid", "succeeded"].includes(status);
}

function orderStatusPending(status: string): boolean {
  return ["pending", "waiting_for_capture", "new", "created"].includes(status);
}

export type DeriveFunnelDetail = {
  pipeline_status: string;
  b2c_status: string;
  consent_accepted?: boolean;
  next_action_at?: string | null;
  waiting_on?: string | null;
  client: { max_linked?: boolean; web_linked?: boolean; preferred_channel?: string };
  documents: { doc_type?: string | null; storage_path?: string; created_at?: string }[];
  checklist_items: { title?: string; status?: string; item_type?: string }[];
  findings?: unknown[];
  analysis_notes?: string | null;
  draft?: { title?: string; body?: string } | null;
  orders?: { status?: string; code?: string | null; amount_rub?: number | null }[];
  orders_summary?: { status?: string; code?: string | null; amount_rub?: number | null }[];
  audit?: { action: string; at?: string }[];
  document_check?: {
    status?: string | null;
    primary_action?: string | null;
    result?: { next_action?: string | null } | null;
  } | null;
};

export function deriveFunnel(detail: DeriveFunnelDetail): {
  stages: FunnelStage[];
  current: FunnelStageId;
  docsReady: boolean;
  docsRequiredOk: boolean;
  hasIls: boolean;
  hasLabor: boolean;
  consentOk: boolean;
  channelOk: boolean;
  diagnosticsDone: boolean;
  serviceConsentOk: boolean;
  missingDocs: string[];
  paymentKnown: "none" | "pending" | "paid" | "unknown";
} {
  const consentOk = Boolean(detail.consent_accepted) || detail.b2c_status !== "lead";
  const channelOk = Boolean(detail.client.max_linked || detail.client.web_linked);
  const items = detail.checklist_items || [];
  const docs = detail.documents || [];

  const hasIls =
    hasDocType(docs, ["ils", "илс", "сзи"]) || checklistDone(items, /илс|выписк/i);
  const hasLabor =
    hasDocType(docs, ["workbook", "labor", "труд", "employment"]) ||
    checklistDone(items, /труд|стаж/i);
  const docsReady =
    docs.length > 0 ||
    [
      "documents_received",
      "ocr_done",
      "classified",
      "extracted",
      "audited",
      "draft_ready",
      "human_review",
      "completed",
    ].includes(detail.pipeline_status);
  const docsRequiredOk = hasIls && hasLabor;
  const missingDocs: string[] = [];
  if (!hasIls) missingDocs.push("выписка ИЛС");
  if (!hasLabor) missingDocs.push("трудовая / сведения о стаже");

  const hasDiagnosisReport = hasDocType(docs, ["diagnosis_report", "диагностик"]);
  const precheckDone = Boolean(
    detail.document_check?.status === "needs_action" ||
      detail.document_check?.status === "succeeded" ||
      detail.document_check?.result ||
      detail.analysis_notes ||
      (detail.findings && detail.findings.length > 0),
  );
  const diagnosticsDone = Boolean(
    hasDiagnosisReport ||
      detail.analysis_notes ||
      (detail.findings && detail.findings.length > 0) ||
      ["audited", "draft_ready", "human_review", "completed"].includes(detail.pipeline_status),
  );

  const orders = detail.orders || detail.orders_summary || [];
  const anyPaid = orders.some((o) => orderStatusPaid(String(o.status || "")));
  const anyPending = orders.some((o) => orderStatusPending(String(o.status || "")));
  let paymentKnown: "none" | "pending" | "paid" | "unknown" = "none";
  if (anyPaid) paymentKnown = "paid";
  else if (anyPending) paymentKnown = "pending";
  else if (orders.length > 0) paymentKnown = "unknown";

  const audit = detail.audit || [];
  const serviceConsentOk =
    detail.b2c_status !== "lead" ||
    audit.some((a) => a.action === "service_consent_recorded");

  const resultDone = ["result_confirmed", "success_fee_due", "success_fee_paid", "closed"].includes(
    detail.b2c_status,
  );
  const feedbackDone = detail.b2c_status === "closed";
  const submissionLikely = [
    "awaiting_client_submission",
    "result_pending",
    "result_confirmed",
    "package_delivered",
  ].includes(detail.b2c_status);
  const packageDelivered = ["package_delivered", "awaiting_client_submission", "result_pending"].includes(
    detail.b2c_status,
  );

  // Текущий фокус — эвристика по фактам; не новый backend-статус.
  let current: FunnelStageId = "contact_consents";
  if (!channelOk || !consentOk) current = "contact_consents";
  else if (!docsReady || (!hasIls && !hasLabor && docs.length === 0)) current = "documents";
  else if (!precheckDone && !diagnosticsDone) current = "precheck_summary";
  else if (paymentKnown !== "paid" && detail.b2c_status !== "lead") current = "analysis_payment";
  else if (!hasDiagnosisReport && !diagnosticsDone) current = "full_analysis";
  else if (!serviceConsentOk) current = "appeals_consent";
  else if (!packageDelivered && !resultDone) current = "appeals_documents";
  else if (submissionLikely && !resultDone) current = "submission";
  else if (!resultDone) current = "follow_up";
  else if (resultDone && !feedbackDone) current = "response_review";
  else current = "closure";

  const wait = detail.waiting_on || "";
  const overdue = isOverdue(detail.next_action_at);
  const curIdx = FUNNEL_STAGE_ORDER.indexOf(current);

  const doneFlags: Record<FunnelStageId, boolean> = {
    contact_consents: channelOk && consentOk,
    documents: docsReady && (hasIls || hasLabor || docs.length > 0),
    precheck_summary: precheckDone || diagnosticsDone,
    analysis_payment: paymentKnown === "paid",
    full_analysis: Boolean(hasDiagnosisReport) || diagnosticsDone,
    appeals_consent: serviceConsentOk && detail.b2c_status !== "lead",
    appeals_payment: false, // отдельный заказ 5k — не выводим из «любой paid»
    appeals_documents: Boolean(detail.draft?.body) || packageDelivered,
    submission: submissionLikely || resultDone,
    follow_up: resultDone,
    response_review: resultDone,
    escalation_package: false,
    closure: feedbackDone,
  };

  const capability: Record<FunnelStageId, FunnelStageCapability> = {
    contact_consents: "live",
    documents: "live",
    precheck_summary: "partial",
    analysis_payment: "partial",
    full_analysis: "partial",
    appeals_consent: "partial",
    appeals_payment: "not_wired",
    appeals_documents: "partial",
    submission: "not_wired",
    follow_up: "not_wired",
    response_review: "partial",
    escalation_package: "not_wired",
    closure: "partial",
  };

  function summaryFor(id: FunnelStageId): string {
    switch (id) {
      case "contact_consents":
        return consentOk && channelOk ? "Канал и согласие ПДн ок" : "Требуется действие";
      case "documents":
        return `${docs.length} файл(ов)` + (missingDocs.length ? ` · нет: ${missingDocs.join(", ")}` : "");
      case "precheck_summary":
        return detail.document_check?.status
          ? `Проверка: ${detail.document_check.status}`
          : precheckDone
            ? "Есть материалы проверки"
            : "Ещё не запускалась";
      case "analysis_payment":
        if (paymentKnown === "paid") return "Оплата подтверждена (есть заказ paid)";
        if (paymentKnown === "pending") return "Ожидается оплата";
        if (paymentKnown === "unknown") return "Статус оплаты не удалось однозначно определить";
        return "Заказ не создан";
      case "full_analysis":
        return hasDiagnosisReport ? "Есть PDF результата" : "Полный результат не выдан";
      case "appeals_consent":
        return serviceConsentOk ? "Согласие на услугу зафиксировано" : "Нужно согласование";
      case "appeals_payment":
        return "Функция ещё не подключена";
      case "appeals_documents":
        return detail.draft?.body ? "Есть черновик" : "Обращения не подготовлены";
      case "submission":
        return "Функция ещё не подключена";
      case "follow_up":
        return "Функция ещё не подключена";
      case "response_review":
        return resultDone ? "Результат зафиксирован" : "Ответа СФР нет";
      case "escalation_package":
        return "Пока не определено";
      case "closure":
        return feedbackDone ? "Дело закрыто" : "Не завершено";
      default:
        return "";
    }
  }

  const stages: FunnelStage[] = FUNNEL_STAGE_ORDER.map((id) => {
    const idx = FUNNEL_STAGE_ORDER.indexOf(id);
    let state: FunnelStageState = "todo";
    let reason = "";
    let canAct = false;
    const cap = capability[id];

    if (cap === "not_wired" && !doneFlags[id]) {
      state = id === current ? "current" : "todo";
      reason = "Функция ещё не подключена";
      canAct = false;
    } else if (id === current) {
      state = overdue ? "overdue" : "current";
      canAct = cap === "live" || cap === "partial";
      if (id === "documents" && !docsRequiredOk) {
        reason = `Не хватает: ${missingDocs.join(", ")}`;
      } else if (id === "precheck_summary" && !docsRequiredOk) {
        state = "blocked";
        canAct = false;
        reason = `Для проверки не хватает: ${missingDocs.join(", ")}`;
      } else if (id === "analysis_payment" && paymentKnown === "unknown") {
        reason = "Статус оплаты неизвестен — сверьте заказ вручную";
      } else if (wait === "client" || wait === "archive" || wait === "sfr" || wait === "payment") {
        state = overdue ? "overdue" : "waiting";
        reason =
          wait === "client"
            ? "Ждём клиента"
            : wait === "archive"
              ? "Ждём архив"
              : wait === "sfr"
                ? "Ждём ответ СФР"
                : "Ждём оплату";
      } else {
        reason = overdue ? "Срок просрочен" : summaryFor(id);
      }
    } else if (doneFlags[id] || idx < curIdx) {
      state = "done";
      reason = "Этап завершён или пройден по фактам";
      canAct = false;
    } else if (cap === "optional") {
      state = "todo";
      reason = "Не требуется / пока не определено";
    } else {
      state = "todo";
      canAct = false;
      if (id === "precheck_summary" && !docsRequiredOk) {
        state = "blocked";
        reason = `Не хватает: ${missingDocs.join(", ")}`;
      } else if (cap === "not_wired") {
        reason = "Функция ещё не подключена";
      } else {
        reason = "Ещё не наступил";
      }
    }

    return {
      id,
      label: LABELS[id],
      state,
      reason,
      canAct,
      shortSummary: summaryFor(id),
      capability: cap,
    };
  });

  return {
    stages,
    current,
    docsReady,
    docsRequiredOk,
    hasIls,
    hasLabor,
    consentOk,
    channelOk,
    diagnosticsDone,
    serviceConsentOk,
    missingDocs,
    paymentKnown,
  };
}

export function primaryCtaLabel(current: FunnelStageId, docsReady: boolean): string {
  if (current === "contact_consents") return "Настроить канал связи";
  if (current === "documents") return docsReady ? "Запустить проверку" : "Запросить документы";
  if (current === "precheck_summary") return "Открыть результат проверки";
  if (current === "analysis_payment") return "Открыть оплату";
  if (current === "full_analysis") return "Открыть подробный анализ";
  if (current === "appeals_consent") return "Зафиксировать согласие";
  if (current === "appeals_payment") return "Оплата обращений (не подключено)";
  if (current === "appeals_documents") return "Открыть обращения";
  if (current === "submission") return "Подача (не подключено)";
  if (current === "follow_up") return "Контроль (не подключено)";
  if (current === "response_review") return "Зафиксировать ответ СФР";
  if (current === "escalation_package") return "Доп. пакет (не подключено)";
  return "Итог дела";
}

export function slaHint(detail: {
  waiting_on?: string | null;
  next_action_at?: string | null;
}): string {
  const wait = detail.waiting_on || "";
  if (wait === "client") return "Ждём клиента";
  if (wait === "archive") return "Ждём архив";
  if (wait === "sfr") return "Ждём ответ СФР";
  if (wait === "payment") return "Ждём оплату";
  if (detail.next_action_at) {
    const due = new Date(detail.next_action_at);
    if (!Number.isNaN(due.getTime())) {
      const diffH = (due.getTime() - Date.now()) / 36e5;
      if (diffH < 0)
        return `Просрочено с ${due.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}`;
      if (diffH < 24)
        return `Срок сегодня ${due.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}`;
      return `Срок ${due.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}`;
    }
  }
  if (wait === "staff") return "Ответить в приоритете";
  return "Срок не задан";
}

export const DOC_REQUEST_ILS =
  "Здравствуйте! Для проверки нужна выписка ИЛС с Госуслуг. Можно прислать файл (PDF/JPG/PNG) прямо в этот чат — примем, специалист увидит. Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. Решение принимает СФР.";

export const DOC_REQUEST_LABOR =
  "Здравствуйте! Подготовьте трудовую книжку или сведения о стаже. Можно прислать сканы (PDF/JPG/PNG) прямо в этот чат — примем, специалист увидит. Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. Решение принимает СФР.";

export const PLAN_READY_CHAT =
  "Подготовили материалы по вашему делу. Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. Решение принимает СФР. Если удобно — ответьте в этот чат.";

export const SERVICE_DESCRIPTION_CHAT =
  "Кратко об услуге: разбираем документы о стаже, готовим понятное резюме и при согласии — проекты обращений. Подачу через СФР/Госуслуги выполняете вы; решение принимает СФР.";
