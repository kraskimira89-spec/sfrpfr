/**
 * Единственная граница: DTO карточки дела → FunnelFacts.
 * Поля без подтверждённого источника → unknown.
 * Не выводить оплату / выдачу / подачу из одного b2c-статуса.
 */

import { buildFunnel } from "./case-funnel-adapter";
import {
  selectCurrentStage,
  viewsToFunnelStages,
  type FunnelStage,
} from "./case-funnel";
import type {
  ActionId,
  FunnelFacts,
  OrderFacts,
  StageId,
  WorkFacts,
} from "./case-funnel-types";
import { looksLikeBriefSummaryChat } from "./format-brief-chat";

/** Подтверждённые факты ступеней 7–13, если API их отдаёт отдельно. */
export type AdditionalCaseFacts = {
  appealsDocuments?: {
    state: WorkFacts["state"];
    releaseReady: WorkFacts["releaseReady"];
  };
  submission?: FunnelFacts["submission"];
  followUp?: FunnelFacts["followUp"];
  response?: FunnelFacts["response"];
  escalation?: Partial<FunnelFacts["escalation"]>;
  closure?: FunnelFacts["closure"];
  preferredStageId?: StageId;
};

export type CaseFunnelDetailInput = {
  pipeline_status: string;
  b2c_status: string;
  consent_accepted?: boolean;
  next_action?: string | null;
  next_action_at?: string | null;
  waiting_on?: string | null;
  silent_days?: number;
  loss_reason?: string | null;
  closed_at?: string | null;
  client: {
    max_linked?: boolean;
    web_linked?: boolean;
    phone?: string | null;
    email?: string | null;
    preferred_channel?: string;
  };
  documents: {
    doc_type?: string | null;
    storage_path?: string;
    ingest_status?: string | null;
    ingest_review_required?: boolean | null;
  }[];
  checklist_items?: { title?: string; status?: string; item_type?: string }[];
  draft?: { title?: string; body?: string } | null;
  orders?: {
    package_code?: string;
    amount_rub?: number;
    status?: string;
    finance_status?: string;
  }[];
  /** false / отсутствие массива → order.state = unknown, не not_ordered. */
  ordersLoaded?: boolean;
  audit?: { action: string; at?: string }[];
  /** Сообщения чата дела — чтобы понять, ушло ли краткое резюме клиенту. */
  chat_messages?: { author_kind?: string; body?: string }[];
  document_check?: {
    status?: string | null;
    stale?: boolean | null;
    result?: {
      missing_for_task?: string[];
      needs_manual_review?: number;
      needs_recognition?: number;
      honest_brief?: {
        current?: boolean;
        has_justified_discrepancy?: boolean;
        offer_diag_allowed?: boolean;
        offer_amount_rub?: number;
        items?: { evidence?: string }[];
      } | null;
      diag_offer?: { allowed?: boolean; amount_rub?: number } | null;
    } | null;
  } | null;
  role_capabilities?: {
    can_edit_pipeline?: boolean;
    can_edit_checklist?: boolean;
    can_confirm_result?: boolean;
    can_manage_orders?: boolean;
    can_view_ocr?: boolean;
    can_knowledge_feedback?: boolean;
  };
  additionalFacts?: AdditionalCaseFacts;
};

function summaryDeliveryOf(
  detail: CaseFunnelDetailInput,
): FunnelFacts["precheck"]["summaryDelivery"] {
  const actions = (detail.audit || []).map((a) => String(a.action || ""));
  if (actions.some((a) => a === "brief_summary_sent" || a.startsWith("brief_summary_sent:"))) {
    return "confirmed";
  }
  const msgs = detail.chat_messages || [];
  const staffSentBrief = msgs.some((m) => {
    const kind = String(m.author_kind || "").toLowerCase();
    if (kind !== "staff" && kind !== "system") return false;
    return looksLikeBriefSummaryChat(m.body);
  });
  if (staffSentBrief) return "confirmed";

  const checkDone = ["completed", "done", "success", "needs_action"].includes(
    String(detail.document_check?.status || "").toLowerCase(),
  );
  // Оплаченная диагностика = клиент уже прошёл офер после резюме; этап 3 не держим синим.
  // Подстановка текста в поле чата сюда не входит — только факт оплаты DIAG.
  const diagPaid = (detail.orders || []).some((o) => {
    if (String(o.package_code || "").toUpperCase() !== "DIAG") return false;
    const st = String(o.status || "").toLowerCase();
    return st === "paid" || st === "succeeded";
  });
  if (checkDone && diagPaid) return "confirmed";

  if (checkDone && detail.document_check?.result?.honest_brief) return "not_sent";
  return "unknown";
}

function hasDocType(
  docs: CaseFunnelDetailInput["documents"],
  needles: string[],
): boolean {
  return docs.some((d) => {
    const t = `${d.doc_type || ""} ${d.storage_path || ""}`.toLowerCase();
    return needles.some((n) => t.includes(n));
  });
}

function checklistDone(
  items: { title?: string; status?: string }[],
  needle: RegExp,
): boolean {
  const matched = items.filter((i) => needle.test(String(i.title || "")));
  if (matched.length === 0) return false;
  return matched.every((i) => i.status === "done");
}

function mapOrderState(status: string): OrderFacts["state"] {
  const s = status.toLowerCase();
  if (["paid", "succeeded"].includes(s)) return "paid";
  if (["pending", "waiting_for_capture", "new", "created", "pending_payment"].includes(s)) {
    return "pending";
  }
  if (["canceled", "cancelled"].includes(s)) return "canceled";
  if (["refunded", "refund"].includes(s)) return "refunded";
  if (!s) return "unknown";
  return "unknown";
}

function pickOrder(
  orders: NonNullable<CaseFunnelDetailInput["orders"]>,
  pred: (o: NonNullable<CaseFunnelDetailInput["orders"]>[number]) => boolean,
): OrderFacts {
  const matches = orders.filter(pred);
  if (matches.length === 0) {
    return { state: "not_ordered", entitlement: "none" };
  }
  const ranked = [...matches].sort((a, b) => {
    const rank = (s: string) => {
      const m = mapOrderState(s);
      if (m === "paid") return 0;
      if (m === "pending") return 1;
      if (m === "refunded") return 2;
      return 3;
    };
    return rank(String(a.status || "")) - rank(String(b.status || ""));
  });
  const best = ranked[0];
  const state = mapOrderState(String(best.status || ""));
  const amount =
    typeof best.amount_rub === "number" && Number.isFinite(best.amount_rub)
      ? best.amount_rub
      : undefined;
  let entitlement: OrderFacts["entitlement"] = "none";
  if (state === "paid") {
    const fin = String(best.finance_status || "").toLowerCase();
    if (!fin || fin === "paid" || fin === "succeeded" || fin === "ok") {
      entitlement = "granted";
    } else if (fin === "unknown" || fin === "error") {
      entitlement = "unknown";
    } else {
      entitlement = "granted";
    }
  } else if (state === "unknown") {
    entitlement = "unknown";
  }
  return { state, amountRub: amount, entitlement };
}

function emptyOrderUnknown(): OrderFacts {
  return { state: "unknown", entitlement: "unknown" };
}

function emptyOrderNone(): OrderFacts {
  return { state: "not_ordered", entitlement: "none" };
}

function unknownWork(): WorkFacts {
  return { state: "unknown", releaseReady: "unknown" };
}

function notStartedWork(): WorkFacts {
  return { state: "not_started", releaseReady: "unknown" };
}

const ALL_ACTIONS: ActionId[] = [
  "edit_contacts",
  "upload_documents",
  "run_precheck",
  "view_precheck",
  "send_summary",
  "open_analysis_order",
  "open_analysis",
  "request_appeals_consent",
  "open_appeals_order",
  "open_appeals",
  "record_submission",
  "schedule_call",
  "record_follow_up",
  "review_response",
  "open_escalation",
  "review_closure",
];

function allowedActionsFromCaps(
  caps: CaseFunnelDetailInput["role_capabilities"],
): ActionId[] {
  if (!caps) return ALL_ACTIONS;
  return ALL_ACTIONS.filter((a) => {
    if (a === "run_precheck" || a === "view_precheck" || a === "open_analysis") {
      return caps.can_view_ocr !== false;
    }
    if (
      a === "open_analysis_order" ||
      a === "open_appeals_order" ||
      a === "open_escalation"
    ) {
      return caps.can_manage_orders !== false;
    }
    if (a === "review_closure") return caps.can_knowledge_feedback !== false;
    if (a === "review_response") return caps.can_confirm_result !== false;
    return true;
  });
}

export function toFunnelFacts(
  detail: CaseFunnelDetailInput,
  additionalFacts: AdditionalCaseFacts = {},
): FunnelFacts {
  const extra = { ...detail.additionalFacts, ...additionalFacts };
  const docs = detail.documents || [];
  const items = detail.checklist_items || [];
  const ordersLoaded = detail.ordersLoaded !== false && Array.isArray(detail.orders);
  const orders = detail.orders || [];

  const hasIls =
    hasDocType(docs, ["ils", "илс", "сзи"]) || checklistDone(items, /илс|выписк/i);
  const hasLabor =
    hasDocType(docs, ["workbook", "labor", "труд", "employment"]) ||
    checklistDone(items, /труд|стаж/i);
  const processing = docs.some((d) =>
    ["pending", "processing", "queued", "running"].includes(
      String(d.ingest_status || "").toLowerCase(),
    ),
  );
  // Ручная проверка / пересъёмка ждут сотрудника — это не «идёт обработка».
  const docsAwaitStaff = docs.some((d) => Boolean(d.ingest_review_required));
  const check = detail.document_check;
  const missing = check?.result?.missing_for_task ?? [];
  const checkDone = ["completed", "succeeded", "done"].includes(
    String(check?.status || "").toLowerCase(),
  );
  // После успешной «Проверить документы» очередь 2.4 не держит ступень 2
  // в «уточнить комплект»: комплект уже оценён, сотрудник идёт к резюме.
  const needsAttention =
    Boolean(check?.stale) ||
    missing.length > 0 ||
    (!checkDone &&
      (docsAwaitStaff ||
        (check?.result?.needs_manual_review ?? 0) > 0 ||
        (check?.result?.needs_recognition ?? 0) > 0));

  const channelOk = Boolean(detail.client.max_linked || detail.client.web_linked);
  const hasContact = Boolean(detail.client.phone || detail.client.email || channelOk);

  let contact: FunnelFacts["contact"] = "unknown";
  if (detail.consent_accepted === true && hasContact && channelOk) {
    contact = "complete";
  } else if (detail.consent_accepted === false || (hasContact && !channelOk)) {
    contact = "incomplete";
  } else if (hasContact && detail.consent_accepted === undefined) {
    // Согласие не пришло в DTO — не имитируем complete.
    contact = "unknown";
  } else if (!hasContact) {
    contact = "incomplete";
  }

  let documents: FunnelFacts["documents"] = "unknown";
  if (docs.length === 0 && items.length === 0) {
    documents = "missing";
  } else if (processing) {
    documents = "processing";
  } else if (!hasIls || !hasLabor || needsAttention) {
    documents = "needs_action";
  } else {
    documents = "ready";
  }

  let precheckState: FunnelFacts["precheck"]["state"] = "not_started";
  if (!check) {
    precheckState = "not_started";
  } else {
    const st = String(check.status || "").toLowerCase();
    if (["queued", "pending"].includes(st)) precheckState = "queued";
    else if (["running", "processing", "in_progress"].includes(st)) precheckState = "running";
    else if (["failed", "error"].includes(st)) precheckState = "failed";
    else if (["succeeded", "done", "needs_action", "completed"].includes(st)) {
      precheckState = "completed";
    } else if (st) precheckState = "unknown";
  }

  let outcome: FunnelFacts["precheck"]["outcome"] = "unknown";
  const brief = check?.result?.honest_brief;
  // Темы анкеты / слова клиента — повод уточнить, не «расхождение между источниками».
  const briefItems = brief?.items ?? [];
  const docEvidence = briefItems.some((i) => i.evidence === "docs");
  if (precheckState === "completed" && brief) {
    if (brief.has_justified_discrepancy && docEvidence) outcome = "discrepancies";
    else if (
      briefItems.length > 0 ||
      missing.length > 0 ||
      (check?.result?.needs_manual_review ?? 0) > 0
    ) {
      outcome = "clarify";
    } else {
      outcome = "clear";
    }
  }

  let analysisNeed: FunnelFacts["analysis"]["need"] = "unknown";
  if (
    docEvidence &&
    (brief?.offer_diag_allowed === true || check?.result?.diag_offer?.allowed === true)
  ) {
    analysisNeed = "recommended";
  } else if (outcome === "clear" && precheckState === "completed" && !check?.stale) {
    analysisNeed = "not_needed";
  }

  let analysisOrder = !ordersLoaded
    ? emptyOrderUnknown()
    : pickOrder(orders, (o) => String(o.package_code || "").toUpperCase() === "DIAG");

  if (ordersLoaded && analysisOrder.state === "not_ordered" && brief?.offer_amount_rub) {
    analysisOrder = {
      ...analysisOrder,
      amountRub: brief.offer_amount_rub,
    };
  }

  const accomp = ordersLoaded
    ? orders.filter((o) => String(o.package_code || "").toUpperCase() === "ACCOMP")
    : [];
  let appealsOrder: OrderFacts = !ordersLoaded ? emptyOrderUnknown() : emptyOrderNone();
  let escalationOrder: OrderFacts = !ordersLoaded ? emptyOrderUnknown() : emptyOrderNone();
  if (ordersLoaded) {
    const by5 = accomp.filter((o) => Number(o.amount_rub) === 5000);
    const by8Legacy = accomp.filter((o) => Number(o.amount_rub) === 8000);
    const ambiguous = accomp.filter(
      (o) => Number(o.amount_rub) !== 5000 && Number(o.amount_rub) !== 8000,
    );
    appealsOrder = by5.length
      ? pickOrder(by5, () => true)
      : ambiguous.length
        ? emptyOrderUnknown()
        : emptyOrderNone();
    // SUPPORT — канон 8k; старые ACCOMP×8000 не переклассифицируем, только читаем.
    const supportRows = orders.filter(
      (o) => String(o.package_code || "").toUpperCase() === "SUPPORT",
    );
    escalationOrder = supportRows.length
      ? pickOrder(supportRows, () => true)
      : by8Legacy.length
        ? pickOrder(by8Legacy, () => true)
        : emptyOrderNone();
  }

  // Этап 5: закрытие только после согласования актуальной версии клиентом.
  // Генерация / DOCX / отправка сами по себе этап не закрывают.
  // Смотрим только события по max(version:N): approve v1 не закрывает этап при version:2.
  const faAudit = (detail.audit || []).filter((a) =>
    String(a.action || "").startsWith("full_analysis_"),
  );
  let analysisWork: WorkFacts = notStartedWork();
  let maxFaVersion = 0;
  for (const row of faAudit) {
    const vm = String(row.action || "").match(/full_analysis_version:(\d+)/);
    if (vm) maxFaVersion = Math.max(maxFaVersion, Number(vm[1]));
  }
  const faScope =
    maxFaVersion > 0
      ? faAudit.filter((row) => {
          const m = String(row.action || "").match(/:(\d+)(?::|$)/);
          return m != null && Number(m[1]) === maxFaVersion;
        })
      : faAudit;
  const latestFa = faScope[0]?.action || "";
  if (/^full_analysis_approved(?::|$)/.test(latestFa)) {
    analysisWork = { state: "delivered", releaseReady: "yes" };
  } else if (
    /^full_analysis_(remarks|sent|reviewed|client_revision|version)(?::|$)/.test(
      latestFa,
    )
  ) {
    analysisWork = {
      state: latestFa.startsWith("full_analysis_version") ? "working" : "ready",
      releaseReady: "no",
    };
  } else {
    const hasDiagnosisFile = hasDocType(docs, ["diagnosis_report", "диагностик"]);
    const publishedDiagnosis = (detail.audit || []).some((a) =>
      /diagnos(is|tic).*publish|publish.*diagnos|diagnosis_published/i.test(a.action),
    );
    // Legacy PDF-публикация: файл готов к выдаче, но не «согласовано клиентом».
    if (publishedDiagnosis || hasDiagnosisFile) {
      analysisWork = { state: "ready", releaseReady: "no" };
    } else if (analysisOrder.entitlement === "granted") {
      analysisWork = notStartedWork();
    } else if (analysisOrder.state === "unknown") {
      analysisWork = unknownWork();
    }
  }

  // Согласие на объём обращений — только audit appeals_consent_*; не из service_consent / чата.
  // Префикс: bot-actor пишет суффикс `:bot:…` в action.
  let appealsConsent: FunnelFacts["appeals"]["consent"] = "unknown";
  const appealsConsentActions = (detail.audit || []).map((a) => String(a.action || ""));
  if (appealsConsentActions.some((a) => a.startsWith("appeals_consent_accepted"))) {
    appealsConsent = "accepted";
  } else if (appealsConsentActions.some((a) => a.startsWith("appeals_consent_declined"))) {
    appealsConsent = "declined";
  } else if (appealsConsentActions.some((a) => a.startsWith("appeals_consent_thinking"))) {
    appealsConsent = "pending";
  }

  const hasDraft = Boolean(detail.draft?.body);
  let appealsWork: WorkFacts = notStartedWork();
  if (extra.appealsDocuments) {
    appealsWork = {
      state: extra.appealsDocuments.state,
      releaseReady: extra.appealsDocuments.releaseReady,
    };
  } else if (hasDraft) {
    // Один draft без реестра исходящих — не releaseReady.
    appealsWork = { state: "working", releaseReady: "no" };
  }

  // Подача / follow-up / response — только из additionalFacts; иначе unknown.
  let submission: FunnelFacts["submission"] = "unknown";
  if (extra.submission !== undefined) submission = extra.submission;

  let followUp: FunnelFacts["followUp"] = {
    state: "unknown",
    callRequired: false,
  };
  if (extra.followUp) followUp = extra.followUp;

  let response: FunnelFacts["response"] = "unknown";
  if (extra.response !== undefined) response = extra.response;

  let escalationNeed: FunnelFacts["escalation"]["need"] = "unknown";
  let escalationConsent: FunnelFacts["escalation"]["consent"] = "unknown";
  let escalationWork: WorkFacts = notStartedWork();
  if (extra.escalation) {
    if (extra.escalation.need) escalationNeed = extra.escalation.need;
    if (extra.escalation.consent) escalationConsent = extra.escalation.consent;
    if (extra.escalation.order) escalationOrder = extra.escalation.order;
    if (extra.escalation.work) escalationWork = extra.escalation.work;
  }

  // Закрытие — только явный факт (closed_at / b2c closed / additional).
  let closure: FunnelFacts["closure"] = { state: "open" };
  if (extra.closure) {
    closure = extra.closure;
  } else if (detail.b2c_status === "closed" || Boolean(detail.closed_at)) {
    closure = {
      state: "closed",
      reason: detail.loss_reason || undefined,
    };
  }

  return {
    contact,
    documents,
    precheck: {
      state: precheckState,
      stale: Boolean(check?.stale) || brief?.current === false,
      outcome,
      summaryDelivery: summaryDeliveryOf(detail),
    },
    analysis: {
      need: analysisNeed,
      order: analysisOrder,
      work: analysisWork,
    },
    appeals: {
      // После согласования разбора (этап 5) предлагаем объём первичных обращений.
      need: analysisWork.state === "delivered" ? "recommended" : "unknown",
      consent: appealsConsent,
      order: appealsOrder,
      work: appealsWork,
    },
    submission,
    followUp,
    response,
    escalation: {
      need: escalationNeed,
      consent: escalationConsent,
      order: escalationOrder,
      work: escalationWork,
    },
    closure,
    preferredStageId: extra.preferredStageId,
    allowedActions: allowedActionsFromCaps(detail.role_capabilities),
  };
}

export function deriveFunnel(detail: CaseFunnelDetailInput): {
  stages: FunnelStage[];
  current: StageId;
  /** Срочная задача ≠ current (ответ СФР и т.п.). */
  priority: StageId | null;
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
  views: ReturnType<typeof buildFunnel>["stages"];
  facts: FunnelFacts;
  funnel: ReturnType<typeof buildFunnel>;
} {
  const facts = toFunnelFacts(detail);
  const funnel = buildFunnel(facts);
  const overdue = Boolean(
    detail.next_action_at && new Date(detail.next_action_at).getTime() < Date.now(),
  );
  const current =
    funnel.currentStageId ||
    selectCurrentStage(funnel.stages, undefined, {
      closed: facts.closure.state === "closed",
    }) ||
    "contact_consents";
  const priority = funnel.priorityStageId ?? null;
  const stages = viewsToFunnelStages(funnel.stages, current, overdue);

  const docs = detail.documents || [];
  const items = detail.checklist_items || [];
  const hasIls =
    hasDocType(docs, ["ils", "илс", "сзи"]) || checklistDone(items, /илс|выписк/i);
  const hasLabor =
    hasDocType(docs, ["workbook", "labor", "труд", "employment"]) ||
    checklistDone(items, /труд|стаж/i);
  const missingDocs: string[] = [];
  if (!hasIls) missingDocs.push("выписка ИЛС");
  if (!hasLabor) missingDocs.push("трудовая / сведения о стаже");

  const ao = facts.analysis.order.state;
  const paymentKnown =
    ao === "paid" ? "paid" : ao === "pending" ? "pending" : ao === "unknown" ? "unknown" : "none";

  return {
    stages,
    current,
    priority,
    docsReady: docs.length > 0,
    docsRequiredOk: hasIls && hasLabor,
    hasIls,
    hasLabor,
    consentOk: facts.contact === "complete",
    channelOk: Boolean(detail.client.max_linked || detail.client.web_linked),
    diagnosticsDone: facts.precheck.state === "completed" && !facts.precheck.stale,
    serviceConsentOk: (detail.audit || []).some((a) => a.action === "service_consent_recorded"),
    missingDocs,
    paymentKnown,
    views: funnel.stages,
    facts,
    funnel,
  };
}
