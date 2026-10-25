/** Сопоставление DTO карточки дела → FunnelFacts. Без выдуманных paid/delivered. */

import type {
  DeliverableFacts,
  FunnelAction,
  FunnelFacts,
  FunnelStageId,
  OrderFacts,
} from "./case-funnel";
import {
  buildFunnelStages,
  selectCurrentStage,
  viewsToFunnelStages,
  type FunnelStage,
} from "./case-funnel";

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
  /** Если массив заказов не загружен — не подставлять not_ordered. */
  ordersLoaded?: boolean;
  audit?: { action: string; at?: string }[];
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
};

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
  // Предпочитаем paid, затем pending, иначе первый.
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
  // Право на услугу — только при подтверждённой оплате заказа (finance_status, если есть).
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

function allowedActionsFromCaps(
  caps: CaseFunnelDetailInput["role_capabilities"],
): FunnelAction[] {
  const all: FunnelAction[] = [
    "edit_contacts",
    "request_consents",
    "upload_documents",
    "run_precheck",
    "view_precheck",
    "send_summary",
    "view_analysis_order",
    "prepare_analysis",
    "deliver_analysis",
    "request_appeals_consent",
    "view_appeals_order",
    "prepare_appeals",
    "deliver_appeals",
    "record_submission",
    "schedule_call",
    "record_follow_up",
    "review_response",
    "open_escalation",
    "review_closure",
    "view_history",
  ];
  if (!caps) return all;
  return all.filter((a) => {
    if (a === "run_precheck" || a === "view_precheck" || a === "prepare_analysis") {
      return caps.can_view_ocr !== false;
    }
    if (a === "view_analysis_order" || a === "view_appeals_order" || a === "open_escalation") {
      return caps.can_manage_orders !== false;
    }
    if (a === "review_closure") return caps.can_knowledge_feedback !== false;
    if (a === "review_response") return caps.can_confirm_result !== false;
    return true;
  });
}

/**
 * Единственная точка сопоставления DTO → FunnelFacts.
 * Отсутствующие/неоднозначные факты → unknown / not_ordered только когда список заказов реально пуст.
 */
export function toFunnelFacts(detail: CaseFunnelDetailInput): FunnelFacts {
  const docs = detail.documents || [];
  const items = detail.checklist_items || [];
  const ordersLoaded = detail.ordersLoaded !== false && Array.isArray(detail.orders);
  const orders = detail.orders || [];

  const hasIls =
    hasDocType(docs, ["ils", "илс", "сзи"]) || checklistDone(items, /илс|выписк/i);
  const hasLabor =
    hasDocType(docs, ["workbook", "labor", "труд", "employment"]) ||
    checklistDone(items, /труд|стаж/i);
  const processing = docs.some(
    (d) =>
      d.ingest_review_required ||
      ["pending", "processing", "queued", "running"].includes(
        String(d.ingest_status || "").toLowerCase(),
      ),
  );
  const check = detail.document_check;
  const missing = check?.result?.missing_for_task ?? [];
  const needsAttention =
    Boolean(check?.stale) ||
    missing.length > 0 ||
    (check?.result?.needs_manual_review ?? 0) > 0 ||
    (check?.result?.needs_recognition ?? 0) > 0;

  const channelOk = Boolean(detail.client.max_linked || detail.client.web_linked);
  const hasContact = Boolean(detail.client.phone || detail.client.email || channelOk);
  let requiredConsents: FunnelFacts["contacts"]["requiredConsents"] = "unknown";
  if (detail.consent_accepted === true) requiredConsents = "confirmed";
  else if (detail.consent_accepted === false) requiredConsents = "missing";
  else if (detail.b2c_status && detail.b2c_status !== "lead") {
    // Не lead, но флаг согласия не пришёл — не выдумываем confirmed.
    requiredConsents = "unknown";
  } else {
    requiredConsents = "missing";
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
      // needs_action = проверка завершила проход (итог для сотрудника), не «ещё идёт».
      precheckState = "completed";
    } else if (st) precheckState = "unknown";
  }

  let outcome: FunnelFacts["precheck"]["outcome"] = "unknown";
  const brief = check?.result?.honest_brief;
  if (precheckState === "completed" && brief) {
    if (brief.has_justified_discrepancy) outcome = "discrepancies";
    else if ((check?.result?.missing_for_task ?? []).length > 0) outcome = "need_documents";
    else if ((check?.result?.needs_manual_review ?? 0) > 0) outcome = "staff_review";
    else outcome = "clear";
  } else if (precheckState === "completed") {
    outcome = "unknown";
  }

  let recommendation: FunnelFacts["analysis"]["recommendation"] = "unknown";
  if (brief?.offer_diag_allowed === true || check?.result?.diag_offer?.allowed === true) {
    recommendation = "recommended";
  } else if (outcome === "clear" && precheckState === "completed" && !check?.stale) {
    recommendation = "not_needed";
  } else if (outcome === "need_documents" || outcome === "staff_review") {
    recommendation = "clarify";
  } else if (precheckState === "not_started" || precheckState === "queued" || precheckState === "running") {
    recommendation = "unknown";
  }

  // Заказы: DIAG = анализ; ACCOMP+~5000 = обращения; ACCOMP+~8000 = доп.пакет.
  // При неоднозначности amount — unknown, не угадывать.
  const analysisOrder = !ordersLoaded
    ? emptyOrderUnknown()
    : pickOrder(orders, (o) => String(o.package_code || "").toUpperCase() === "DIAG");

  if (ordersLoaded && analysisOrder.state === "not_ordered" && brief?.offer_amount_rub) {
    analysisOrder.amountRub = brief.offer_amount_rub;
  }

  const accomp = ordersLoaded
    ? orders.filter((o) => String(o.package_code || "").toUpperCase() === "ACCOMP")
    : [];
  let appealsOrder: OrderFacts = !ordersLoaded ? emptyOrderUnknown() : emptyOrderNone();
  let escalationOrder: OrderFacts = !ordersLoaded ? emptyOrderUnknown() : emptyOrderNone();
  if (ordersLoaded) {
    const by5 = accomp.filter((o) => Number(o.amount_rub) === 5000);
    const by8 = accomp.filter((o) => Number(o.amount_rub) === 8000);
    const ambiguous = accomp.filter(
      (o) => Number(o.amount_rub) !== 5000 && Number(o.amount_rub) !== 8000,
    );
    appealsOrder = by5.length
      ? pickOrder(by5, () => true)
      : ambiguous.length
        ? emptyOrderUnknown()
        : emptyOrderNone();
    escalationOrder = by8.length
      ? pickOrder(by8, () => true)
      : ambiguous.length && !by5.length
        ? emptyOrderUnknown()
        : emptyOrderNone();
  }

  const hasDiagnosisFile = hasDocType(docs, ["diagnosis_report", "диагностик"]);
  const publishedDiagnosis = (detail.audit || []).some((a) =>
    /diagnos(is|tic).*publish|publish.*diagnos|diagnosis_published/i.test(a.action),
  );
  let analysisResult: DeliverableFacts = { state: "not_started" };
  if (publishedDiagnosis) analysisResult = { state: "delivered" };
  else if (hasDiagnosisFile) analysisResult = { state: "ready" };
  else if (analysisOrder.entitlement === "granted") analysisResult = { state: "not_started" };

  const serviceConsent = (detail.audit || []).some((a) => a.action === "service_consent_recorded");
  let appealsConsent: FunnelFacts["appeals"]["consent"] = "unknown";
  if (serviceConsent) appealsConsent = "accepted";
  else if (detail.b2c_status === "lead") appealsConsent = "not_requested";
  // иначе unknown — не путать согласие ПДн с согласием на обращения

  const hasDraft = Boolean(detail.draft?.body);
  const appealsPackage: FunnelFacts["appeals"]["package"] = {
    // Один draft ≠ реестр отдельных файлов обращений.
    state: hasDraft ? "working" : "not_started",
    fileCount: hasDraft ? 1 : 0,
    allReviewed: false,
    clientApproved: false,
  };

  let submissionState: FunnelFacts["submission"]["state"] = "unknown";
  const b2c = detail.b2c_status;
  if (b2c === "awaiting_client_submission") submissionState = "awaiting_client";
  else if (["result_pending", "result_confirmed", "success_fee_due", "success_fee_paid", "closed"].includes(b2c)) {
    // result_* не доказывает подтверждённую подачу клиентом — только что процесс ушёл дальше.
    submissionState = "unknown";
  } else if (b2c === "package_delivered") {
    submissionState = "not_started";
  } else {
    submissionState = "not_started";
  }

  // confirmed подачи в DTO пока нет — не активируем follow-up по догадке.
  let followState: FunnelFacts["followUp"]["state"] = "inactive";
  if (submissionState === "unknown") followState = "unknown";
  else if (submissionState === "awaiting_client") followState = "inactive";

  let responseState: FunnelFacts["response"]["state"] = "none";
  if (b2c === "result_pending") responseState = "received";
  else if (["result_confirmed", "success_fee_due", "success_fee_paid", "closed"].includes(b2c)) {
    responseState = "reviewed";
  }

  const closed = b2c === "closed" || Boolean(detail.closed_at);

  return {
    contacts: {
      known: hasContact || requiredConsents !== "unknown",
      reachable: channelOk,
      requiredConsents,
    },
    documents: {
      known: true,
      count: docs.length,
      processing,
      sufficient: hasIls && hasLabor && missing.length === 0,
      needsAttention,
    },
    precheck: {
      state: precheckState,
      stale: Boolean(check?.stale) || brief?.current === false,
      outcome,
      // Доставка резюме клиенту в DTO явно не подтверждена → unknown (не not_sent по умолчанию).
      summaryDelivery: "unknown",
    },
    analysis: {
      recommendation,
      order: analysisOrder,
      result: analysisResult,
    },
    appeals: {
      // План обращений после полного анализа в DTO явно не размечен → unknown.
      need: "unknown",
      consent: appealsConsent,
      order: appealsOrder,
      package: appealsPackage,
    },
    submission: { state: submissionState },
    followUp: {
      state: followState,
      callDue: false,
      nextCheckAt: detail.next_action_at || undefined,
    },
    response: { state: responseState },
    escalation: {
      decision: "unknown",
      consent: "unknown",
      order: escalationOrder,
      result: { state: "not_started" },
    },
    closure: {
      state: closed ? "closed" : "open",
      reason: detail.loss_reason || undefined,
      chronologyReady: false,
    },
    permissions: { allowedActions: allowedActionsFromCaps(detail.role_capabilities) },
  };
}

export function deriveFunnel(detail: CaseFunnelDetailInput): {
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
  views: ReturnType<typeof buildFunnelStages>;
  facts: FunnelFacts;
} {
  const facts = toFunnelFacts(detail);
  const views = buildFunnelStages(facts);
  const overdue = Boolean(
    detail.next_action_at && new Date(detail.next_action_at).getTime() < Date.now(),
  );
  const closed = facts.closure.state === "closed";
  const current =
    selectCurrentStage(views, undefined, { closed }) || views[0]?.id || "contact_consents";
  const stages = viewsToFunnelStages(views, current, overdue);

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
    docsReady: docs.length > 0,
    docsRequiredOk: hasIls && hasLabor,
    hasIls,
    hasLabor,
    consentOk: facts.contacts.requiredConsents === "confirmed",
    channelOk: facts.contacts.reachable,
    diagnosticsDone: facts.precheck.state === "completed" && !facts.precheck.stale,
    serviceConsentOk: facts.appeals.consent === "accepted",
    missingDocs,
    paymentKnown,
    views,
    facts,
  };
}
