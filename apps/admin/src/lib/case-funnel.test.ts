import assert from "node:assert/strict";
import test from "node:test";

import { buildFunnel } from "./case-funnel-adapter.ts";
import { deriveFunnel, toFunnelFacts } from "./case-funnel-facts.ts";
import {
  STAGE_IDS,
  type ActionId,
  type FunnelFacts,
  type OrderFacts,
  type WorkFacts,
} from "./case-funnel-types.ts";

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

function emptyOrder(): OrderFacts {
  return { state: "not_ordered", entitlement: "none" };
}

function work(
  state: WorkFacts["state"] = "not_started",
  releaseReady: WorkFacts["releaseReady"] = "unknown",
): WorkFacts {
  return { state, releaseReady };
}

function baseFacts(over: Partial<FunnelFacts> = {}): FunnelFacts {
  const base: FunnelFacts = {
    contact: "complete",
    documents: "ready",
    precheck: {
      state: "completed",
      stale: false,
      outcome: "discrepancies",
      summaryDelivery: "unknown",
    },
    analysis: {
      need: "recommended",
      order: emptyOrder(),
      work: work(),
    },
    appeals: {
      need: "unknown",
      consent: "not_requested",
      order: emptyOrder(),
      work: work(),
    },
    submission: "unknown",
    receiptVerified: false,
    followUp: { state: "unknown", callRequired: false },
    response: "unknown",
    escalation: {
      need: "unknown",
      consent: "unknown",
      order: emptyOrder(),
      work: work(),
    },
    closure: { state: "open" },
    allowedActions: ALL_ACTIONS,
  };
  return {
    ...base,
    ...over,
    precheck: { ...base.precheck, ...over.precheck },
    analysis: {
      ...base.analysis,
      ...over.analysis,
      order: { ...base.analysis.order, ...over.analysis?.order },
      work: { ...base.analysis.work, ...over.analysis?.work },
    },
    appeals: {
      ...base.appeals,
      ...over.appeals,
      order: { ...base.appeals.order, ...over.appeals?.order },
      work: { ...base.appeals.work, ...over.appeals?.work },
    },
    followUp: { ...base.followUp, ...over.followUp },
    escalation: {
      ...base.escalation,
      ...over.escalation,
      order: { ...base.escalation.order, ...over.escalation?.order },
      work: { ...base.escalation.work, ...over.escalation?.work },
    },
    closure: { ...base.closure, ...over.closure },
    allowedActions: over.allowedActions ?? base.allowedActions,
  };
}

test("ровно 13 уникальных ID", () => {
  const { stages } = buildFunnel(baseFacts());
  assert.equal(stages.length, 13);
  assert.equal(new Set(stages.map((s) => s.id)).size, 13);
  assert.deepEqual(
    stages.map((s) => s.id),
    [...STAGE_IDS],
  );
});

test("unknown оплаты не становится not_ordered", () => {
  const pay = buildFunnel(
    baseFacts({
      analysis: {
        need: "recommended",
        order: { state: "unknown", entitlement: "unknown" },
        work: work(),
      },
    }),
  ).stages.find((s) => s.id === "analysis_payment");
  assert.equal(pay?.status, "unknown");
  assert.match(pay?.summary || "", /недоступен/i);
});

test("оплаченный заказ не скрывается после смены рекомендации", () => {
  const pay = buildFunnel(
    baseFacts({
      analysis: {
        need: "not_needed",
        order: { state: "paid", entitlement: "granted", amountRub: 3000 },
        work: work(),
      },
      precheck: {
        state: "completed",
        stale: true,
        outcome: "clear",
        summaryDelivery: "unknown",
      },
    }),
  ).stages.find((s) => s.id === "analysis_payment");
  assert.equal(pay?.status, "done");
});

test("оплата дополнительного пакета не завершает ступень 12", () => {
  const esc = buildFunnel(
    baseFacts({
      escalation: {
        need: "recommended",
        consent: "accepted",
        order: { state: "paid", entitlement: "none", amountRub: 8000 },
        work: work(),
      },
    }),
  ).stages.find((s) => s.id === "escalation_package");
  assert.notEqual(esc?.status, "done");
  assert.equal(esc?.status, "needs_action");
});

test("готовый файл не считается переданным", () => {
  const full = buildFunnel(
    baseFacts({
      analysis: {
        need: "recommended",
        order: { state: "paid", entitlement: "granted", amountRub: 3000 },
        work: work("ready", "yes"),
      },
    }),
  ).stages.find((s) => s.id === "full_analysis");
  assert.equal(full?.status, "needs_action");
  assert.equal(full?.action, "open_analysis");
});

test("переданный файл не считается поданным в СФР", () => {
  const sub = buildFunnel(
    baseFacts({
      appeals: {
        need: "recommended",
        consent: "accepted",
        order: { state: "paid", entitlement: "granted" },
        work: work("delivered", "yes"),
      },
      submission: "awaiting_client",
    }),
  ).stages.find((s) => s.id === "submission");
  assert.notEqual(sub?.status, "done");
  assert.equal(sub?.status, "waiting");
});

test("закрытие только по явному факту", () => {
  const closure = buildFunnel(
    baseFacts({
      analysis: {
        need: "recommended",
        order: { state: "paid", entitlement: "granted" },
        work: work("delivered", "yes"),
      },
      closure: { state: "open" },
    }),
  ).stages.find((s) => s.id === "closure");
  assert.notEqual(closure?.status, "done");
});

test("закрытие closed → done", () => {
  const closure = buildFunnel(
    baseFacts({ closure: { state: "closed", reason: "успех" } }),
  ).stages.find((s) => s.id === "closure");
  assert.equal(closure?.status, "done");
});

test("allowedActions снимает action", () => {
  const docs = buildFunnel(
    baseFacts({
      documents: "missing",
      allowedActions: [],
    }),
  ).stages.find((s) => s.id === "documents");
  assert.equal(docs?.action, undefined);
});

test("releaseReady=no при ready → needs_action с проверкой", () => {
  const appeals = buildFunnel(
    baseFacts({
      appeals: {
        need: "recommended",
        consent: "accepted",
        order: { state: "paid", entitlement: "granted", amountRub: 5000 },
        work: work("ready", "no"),
      },
    }),
  ).stages.find((s) => s.id === "appeals_documents");
  assert.equal(appeals?.status, "needs_action");
  assert.match(appeals?.summary || "", /проверк/i);
});

test("toFunnelFacts: файлы ждут ручной проверки — это needs_action, не «идёт обработка»", () => {
  const facts = toFunnelFacts({
    pipeline_status: "human_review",
    b2c_status: "in_progress",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [
      { doc_type: "ils", storage_path: "c/ils.pdf", ingest_status: "manual_review", ingest_review_required: true },
      { doc_type: "workbook", storage_path: "c/tk.docx", ingest_status: "needs_reupload", ingest_review_required: true },
    ],
    orders: [],
    ordersLoaded: true,
  });
  assert.equal(facts.documents, "needs_action");
});

test("toFunnelFacts: файл в очереди загрузки — processing", () => {
  const facts = toFunnelFacts({
    pipeline_status: "documents_received",
    b2c_status: "in_progress",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [{ doc_type: "ils", storage_path: "c/ils.pdf", ingest_status: "queued" }],
    orders: [],
    ordersLoaded: true,
  });
  assert.equal(facts.documents, "processing");
});

test("toFunnelFacts: темы анкеты ≠ расхождения документов (нет офера, outcome=clarify)", () => {
  const facts = toFunnelFacts({
    pipeline_status: "human_review",
    b2c_status: "in_progress",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [{ doc_type: "ils", storage_path: "c/ils.pdf" }],
    orders: [],
    ordersLoaded: true,
    document_check: {
      status: "needs_action",
      stale: false,
      result: {
        honest_brief: {
          has_justified_discrepancy: true,
          offer_diag_allowed: true,
          items: [
            { text: "северный стаж", evidence: "needs_check" },
            { text: "даты", evidence: "client" },
          ],
        },
        diag_offer: { allowed: true, amount_rub: 3000 },
      },
    },
  });
  assert.equal(facts.precheck.outcome, "clarify");
  assert.notEqual(facts.analysis.need, "recommended");
});

test("toFunnelFacts: расхождение из документов → discrepancies + recommended", () => {
  const facts = toFunnelFacts({
    pipeline_status: "human_review",
    b2c_status: "in_progress",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [{ doc_type: "ils", storage_path: "c/ils.pdf" }],
    orders: [],
    ordersLoaded: true,
    document_check: {
      status: "completed",
      stale: false,
      result: {
        honest_brief: {
          has_justified_discrepancy: true,
          offer_diag_allowed: true,
          items: [{ text: "период не отражён в ИЛС", evidence: "docs" }],
        },
        diag_offer: { allowed: true, amount_rub: 3000 },
      },
    },
  });
  assert.equal(facts.precheck.outcome, "discrepancies");
  assert.equal(facts.analysis.need, "recommended");
});

test("toFunnelFacts: b2c не превращает в paid", () => {
  const facts = toFunnelFacts({
    pipeline_status: "completed",
    b2c_status: "package_delivered",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [],
    orders: [],
    ordersLoaded: true,
  });
  assert.equal(facts.analysis.order.state, "not_ordered");
  assert.equal(facts.submission, "not_started");
  assert.equal(facts.response, "unknown");
});

test("toFunnelFacts: orders не загружены → unknown, не not_ordered", () => {
  const facts = toFunnelFacts({
    pipeline_status: "human_review",
    b2c_status: "lead",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [],
    ordersLoaded: false,
  });
  assert.equal(facts.analysis.order.state, "unknown");
});

test("toFunnelFacts: файл диагноза → ready, не delivered", () => {
  const facts = toFunnelFacts({
    pipeline_status: "human_review",
    b2c_status: "lead",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [{ doc_type: "diagnosis_report", storage_path: "c/d.pdf" }],
    orders: [{ package_code: "DIAG", amount_rub: 3000, status: "paid" }],
    ordersLoaded: true,
  });
  assert.equal(facts.analysis.work.state, "ready");
  assert.notEqual(facts.analysis.work.state, "delivered");
});

test("toFunnelFacts: этап 5 закрыт только после full_analysis_approved", () => {
  const before = toFunnelFacts({
    pipeline_status: "human_review",
    b2c_status: "lead",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [],
    orders: [{ package_code: "DIAG", amount_rub: 3000, status: "paid" }],
    ordersLoaded: true,
    audit: [
      { action: "full_analysis_sent:1:email" },
      { action: "full_analysis_reviewed:1" },
      { action: "full_analysis_version:1" },
    ],
  });
  assert.equal(before.analysis.work.state, "ready");
  assert.equal(before.analysis.work.releaseReady, "no");

  const after = toFunnelFacts({
    pipeline_status: "human_review",
    b2c_status: "lead",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [],
    orders: [{ package_code: "DIAG", amount_rub: 3000, status: "paid" }],
    ordersLoaded: true,
    audit: [
      { action: "full_analysis_approved:1" },
      { action: "full_analysis_sent:1:email" },
    ],
  });
  assert.equal(after.analysis.work.state, "delivered");
  assert.equal(after.analysis.work.releaseReady, "yes");
});

test("toFunnelFacts: новая версия после замечаний снова не delivered", () => {
  const facts = toFunnelFacts({
    pipeline_status: "human_review",
    b2c_status: "lead",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [],
    orders: [{ package_code: "DIAG", amount_rub: 3000, status: "paid" }],
    ordersLoaded: true,
    audit: [
      { action: "full_analysis_version:2" },
      { action: "full_analysis_remarks:1" },
      { action: "full_analysis_approved:1" },
    ],
  });
  assert.notEqual(facts.analysis.work.state, "delivered");
  assert.equal(facts.analysis.work.state, "working");
});

test("toFunnelFacts: устаревший approve v1 не закрывает этап при version:2", () => {
  const facts = toFunnelFacts({
    pipeline_status: "human_review",
    b2c_status: "lead",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [],
    orders: [{ package_code: "DIAG", amount_rub: 3000, status: "paid" }],
    ordersLoaded: true,
    audit: [
      { action: "full_analysis_approved:1" },
      { action: "full_analysis_version:2" },
      { action: "full_analysis_sent:1:email" },
      { action: "full_analysis_version:1" },
    ],
  });
  assert.notEqual(facts.analysis.work.state, "delivered");
  assert.equal(facts.analysis.work.state, "working");
});

test("toFunnelFacts: additional response none", () => {
  const facts = toFunnelFacts(
    {
      pipeline_status: "human_review",
      b2c_status: "lead",
      consent_accepted: true,
      client: { max_linked: true },
      documents: [],
      orders: [],
      ordersLoaded: true,
    },
    { response: "none" },
  );
  assert.equal(facts.response, "none");
});

test("несохранённые формы не меняют статусы: orderAmount вне facts", () => {
  const a = toFunnelFacts({
    pipeline_status: "human_review",
    b2c_status: "lead",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [],
    orders: [],
    ordersLoaded: true,
  });
  const b = toFunnelFacts({
    pipeline_status: "human_review",
    b2c_status: "lead",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [],
    orders: [],
    ordersLoaded: true,
  });
  assert.deepEqual(a.analysis.order, b.analysis.order);
  assert.equal(a.analysis.order.state, "not_ordered");
});

test("toFunnelFacts: appeals_consent_accepted из audit", () => {
  const facts = toFunnelFacts({
    pipeline_status: "human_review",
    b2c_status: "in_progress",
    client: { max_linked: true },
    documents: [],
    orders: [],
    ordersLoaded: true,
    audit: [{ action: "appeals_consent_accepted" }],
  });
  assert.equal(facts.appeals.consent, "accepted");
});

test("toFunnelFacts: service_consent не даёт appeals.consent accepted", () => {
  const facts = toFunnelFacts({
    pipeline_status: "human_review",
    b2c_status: "in_progress",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [{ doc_type: "ils", storage_path: "c/ils.pdf" }],
    orders: [],
    ordersLoaded: true,
    audit: [{ action: "service_consent_recorded" }],
  });
  assert.equal(facts.appeals.consent, "unknown");
});

test("stage6: после full_analysis_approved need=recommended и без consent → needs_action", () => {
  const funnel = deriveFunnel({
    pipeline_status: "human_review",
    b2c_status: "in_progress",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [],
    orders: [],
    ordersLoaded: true,
    audit: [
      { action: "full_analysis_approved:1" },
      { action: "full_analysis_version:1" },
    ],
  });
  assert.equal(funnel.facts.analysis.work.state, "delivered");
  assert.equal(funnel.facts.appeals.need, "recommended");
  assert.equal(funnel.facts.appeals.consent, "unknown");
  const stage = funnel.funnel.stages.find((s) => s.id === "appeals_consent");
  assert.equal(stage?.status, "needs_action");
});

test("stage6: full_analysis_approved + appeals_consent_accepted → appeals_consent done", () => {
  const funnel = deriveFunnel({
    pipeline_status: "human_review",
    b2c_status: "in_progress",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [],
    orders: [],
    ordersLoaded: true,
    audit: [
      { action: "appeals_consent_accepted" },
      { action: "full_analysis_approved:1" },
      { action: "full_analysis_version:1" },
    ],
  });
  assert.equal(funnel.facts.appeals.need, "recommended");
  assert.equal(funnel.facts.appeals.consent, "accepted");
  const stage = funnel.funnel.stages.find((s) => s.id === "appeals_consent");
  assert.equal(stage?.status, "done");
});

const stage78Base = {
  pipeline_status: "human_review",
  b2c_status: "in_progress",
  consent_accepted: true,
  client: { max_linked: true },
  documents: [],
  ordersLoaded: true as const,
  audit: [
    { action: "appeals_consent_accepted" },
    { action: "full_analysis_approved:1" },
    { action: "full_analysis_version:1" },
  ],
};

test("stage7: согласие без счёта → appeals_payment not_started", () => {
  const funnel = deriveFunnel({ ...stage78Base, orders: [] });
  const pay = funnel.funnel.stages.find((s) => s.id === "appeals_payment");
  assert.equal(pay?.status, "not_started");
});

test("stage7: ACCOMP 5000 pending → appeals_payment waiting", () => {
  const funnel = deriveFunnel({
    ...stage78Base,
    orders: [{ package_code: "ACCOMP", amount_rub: 5000, status: "pending" }],
  });
  const pay = funnel.funnel.stages.find((s) => s.id === "appeals_payment");
  assert.equal(pay?.status, "waiting");
  assert.equal(funnel.facts.appeals.order.state, "pending");
});

test("stage7: ACCOMP 5000 paid → appeals_payment done, entitlement granted", () => {
  const funnel = deriveFunnel({
    ...stage78Base,
    orders: [{ package_code: "ACCOMP", amount_rub: 5000, status: "paid" }],
  });
  const pay = funnel.funnel.stages.find((s) => s.id === "appeals_payment");
  assert.equal(pay?.status, "done");
  assert.equal(funnel.facts.appeals.order.entitlement, "granted");
  const docs = funnel.funnel.stages.find((s) => s.id === "appeals_documents");
  assert.notEqual(docs?.status, "blocked");
});

test("stage8: draft без ready → working / in_progress", () => {
  const funnel = deriveFunnel({
    ...stage78Base,
    orders: [{ package_code: "ACCOMP", amount_rub: 5000, status: "paid" }],
    draft: { title: "Обращение", body: "Текст проекта" },
  });
  assert.equal(funnel.facts.appeals.work.state, "working");
  assert.equal(funnel.facts.appeals.work.releaseReady, "no");
  const docs = funnel.funnel.stages.find((s) => s.id === "appeals_documents");
  assert.equal(docs?.status, "in_progress");
});

test("stage8: appeals_package_ready → ready к передаче", () => {
  const funnel = deriveFunnel({
    ...stage78Base,
    orders: [{ package_code: "ACCOMP", amount_rub: 5000, status: "paid" }],
    draft: { title: "Обращение", body: "Текст" },
    audit: [
      { action: "appeals_package_ready" },
      ...stage78Base.audit,
    ],
  });
  assert.equal(funnel.facts.appeals.work.state, "ready");
  assert.equal(funnel.facts.appeals.work.releaseReady, "yes");
  const docs = funnel.funnel.stages.find((s) => s.id === "appeals_documents");
  assert.equal(docs?.status, "needs_action");
});

test("stage8: appeals_package_delivered → done", () => {
  const funnel = deriveFunnel({
    ...stage78Base,
    orders: [{ package_code: "ACCOMP", amount_rub: 5000, status: "paid" }],
    draft: { title: "Обращение", body: "Текст" },
    audit: [
      { action: "appeals_package_delivered" },
      { action: "appeals_package_ready" },
      ...stage78Base.audit,
    ],
  });
  assert.equal(funnel.facts.appeals.work.state, "delivered");
  const docs = funnel.funnel.stages.find((s) => s.id === "appeals_documents");
  assert.equal(docs?.status, "done");
});

test("stage9: переданный пакет ≠ confirmed (ожидаем клиента)", () => {
  const funnel = deriveFunnel({
    ...stage78Base,
    orders: [{ package_code: "ACCOMP", amount_rub: 5000, status: "paid" }],
    draft: { title: "Обращение", body: "Текст" },
    audit: [
      { action: "appeals_package_delivered" },
      { action: "appeals_package_ready" },
      ...stage78Base.audit,
    ],
  });
  assert.equal(funnel.facts.submission, "awaiting_client");
  const sub = funnel.funnel.stages.find((s) => s.id === "submission");
  assert.equal(sub?.status, "waiting");
  assert.notEqual(sub?.status, "done");
});

test("stage9: submission_confirmed → done", () => {
  const funnel = deriveFunnel({
    ...stage78Base,
    orders: [{ package_code: "ACCOMP", amount_rub: 5000, status: "paid" }],
    draft: { title: "Обращение", body: "Текст" },
    audit: [
      { action: "submission_confirmed" },
      { action: "appeals_package_delivered" },
      { action: "appeals_package_ready" },
      ...stage78Base.audit,
    ],
  });
  assert.equal(funnel.facts.submission, "confirmed");
  const sub = funnel.funnel.stages.find((s) => s.id === "submission");
  assert.equal(sub?.status, "done");
});

test("stage9: submission_help_requested → needs_action", () => {
  const funnel = deriveFunnel({
    ...stage78Base,
    orders: [{ package_code: "ACCOMP", amount_rub: 5000, status: "paid" }],
    draft: { title: "Обращение", body: "Текст" },
    audit: [
      { action: "submission_help_requested" },
      { action: "appeals_package_delivered" },
      ...stage78Base.audit,
    ],
  });
  assert.equal(funnel.facts.submission, "help_requested");
  const sub = funnel.funnel.stages.find((s) => s.id === "submission");
  assert.equal(sub?.status, "needs_action");
});

test("stage9: confirmed открывает follow_up с submittedOn, без dueAt", () => {
  const funnel = deriveFunnel({
    ...stage78Base,
    orders: [{ package_code: "ACCOMP", amount_rub: 5000, status: "paid" }],
    draft: { title: "Обращение", body: "Текст" },
    submission_report: {
      kind: "client_reported",
      submitted_on: "2026-10-20",
      method: "gosuslugi",
      submitted_what: "Пакет",
      proof_missing: true,
    },
    audit: [
      { action: "submission_confirmed" },
      { action: "appeals_package_delivered" },
      ...stage78Base.audit,
    ],
  });
  assert.equal(funnel.facts.submission, "confirmed");
  assert.equal(funnel.facts.submittedOn, "2026-10-20");
  assert.equal(funnel.facts.followUp.state, "active");
  assert.equal(funnel.facts.followUp.submittedOn, "2026-10-20");
  assert.equal(funnel.facts.followUp.dueAt, undefined);
  assert.equal(funnel.facts.receiptVerified, false);
  const follow = funnel.funnel.stages.find((s) => s.id === "follow_up");
  assert.notEqual(follow?.status, "blocked");
});

test("stage10: next_action_at → followUp.dueAt; handoff → completed + response", () => {
  const before = deriveFunnel({
    ...stage78Base,
    orders: [{ package_code: "ACCOMP", amount_rub: 5000, status: "paid" }],
    next_action_at: "2026-11-05T10:00:00+05:00",
    next_action: "Уточнить у клиента",
    audit: [
      { action: "submission_confirmed" },
      { action: "appeals_package_delivered" },
      ...stage78Base.audit,
    ],
  });
  assert.equal(before.facts.followUp.dueAt, "2026-11-05T10:00:00+05:00");
  assert.equal(before.facts.followUp.state, "active");

  const after = deriveFunnel({
    ...stage78Base,
    orders: [{ package_code: "ACCOMP", amount_rub: 5000, status: "paid" }],
    audit: [
      { action: "follow_up_completed" },
      { action: "follow_up_response_handoff" },
      { action: "submission_confirmed" },
      { action: "appeals_package_delivered" },
      ...stage78Base.audit,
    ],
  });
  assert.equal(after.facts.followUp.state, "completed");
  assert.equal(after.facts.response, "received");
  const resp = after.funnel.stages.find((s) => s.id === "response_review");
  assert.notEqual(resp?.status, "blocked");
});

test("stage11: handoff ≠ reviewed; reviews status drives response", () => {
  const handoffOnly = deriveFunnel({
    ...stage78Base,
    orders: [{ package_code: "ACCOMP", amount_rub: 5000, status: "paid" }],
    audit: [
      { action: "follow_up_response_handoff" },
      { action: "submission_confirmed" },
      ...stage78Base.audit,
    ],
  });
  assert.equal(handoffOnly.facts.response, "received");

  const reviewing = deriveFunnel({
    ...stage78Base,
    orders: [{ package_code: "ACCOMP", amount_rub: 5000, status: "paid" }],
    response_reviews: [{ id: "r1", status: "reviewing" }],
    audit: [
      { action: "response_review_registered" },
      { action: "follow_up_response_handoff" },
      { action: "submission_confirmed" },
      ...stage78Base.audit,
    ],
  });
  assert.equal(reviewing.facts.response, "reviewing");

  const reviewed = deriveFunnel({
    ...stage78Base,
    orders: [{ package_code: "ACCOMP", amount_rub: 5000, status: "paid" }],
    response_reviews: [{ id: "r1", status: "reviewed", outcome: "wait_client" }],
    audit: [
      { action: "response_review_outcome:wait_client" },
      { action: "response_review_reviewed" },
      { action: "submission_confirmed" },
      ...stage78Base.audit,
    ],
  });
  assert.equal(reviewed.facts.response, "reviewed");
  const stage = reviewed.funnel.stages.find((s) => s.id === "response_review");
  assert.equal(stage?.status, "done");
});

test("stage9: receipt_verified ≠ путать с confirmed без report", () => {
  const funnel = deriveFunnel({
    ...stage78Base,
    orders: [{ package_code: "ACCOMP", amount_rub: 5000, status: "paid" }],
    audit: [
      { action: "submission_receipt_verified" },
      { action: "submission_confirmed" },
      { action: "appeals_package_delivered" },
      ...stage78Base.audit,
    ],
  });
  assert.equal(funnel.facts.receiptVerified, true);
  assert.equal(funnel.facts.submission, "confirmed");
});

test("deriveFunnel kit + 13 stages", () => {
  const funnel = deriveFunnel({
    pipeline_status: "documents_received",
    b2c_status: "lead",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [
      { doc_type: "ils", storage_path: "c/ils.pdf" },
      { doc_type: "workbook", storage_path: "c/tk.docx" },
    ],
    orders: [],
    ordersLoaded: true,
  });
  assert.equal(funnel.hasIls, true);
  assert.equal(funnel.stages.length, 13);
  assert.equal(funnel.funnel.stages.length, 13);
});

test("toFunnelFacts: после completed проверки ingest_review не держит ступень Документы", () => {
  const facts = toFunnelFacts({
    pipeline_status: "human_review",
    b2c_status: "in_progress",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [
      { doc_type: "ils", storage_path: "c/ils.pdf", ingest_status: "manual_review", ingest_review_required: true },
      { doc_type: "workbook", storage_path: "c/tk.docx", ingest_status: "manual_review", ingest_review_required: true },
    ],
    orders: [],
    ordersLoaded: true,
    document_check: {
      status: "completed",
      stale: false,
      result: {
        missing_for_task: [],
        needs_manual_review: 0,
        needs_recognition: 0,
        honest_brief: {
          has_justified_discrepancy: true,
          items: [{ evidence: "docs", text: "Северный стаж учтён не за весь период" }],
        },
      },
    },
  });
  assert.equal(facts.documents, "ready");
  assert.equal(facts.precheck.outcome, "discrepancies");
});

test("precheck_summary: после отправки краткого резюме — done (зелёный)", () => {
  const base = {
    pipeline_status: "human_review",
    b2c_status: "in_progress",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [{ doc_type: "ils", storage_path: "c/ils.pdf" }],
    orders: [] as { package_code: string; amount_rub: number; status: string }[],
    ordersLoaded: true,
    document_check: {
      status: "completed",
      stale: false,
      result: {
        honest_brief: {
          has_justified_discrepancy: true,
          offer_diag_allowed: true,
          items: [{ text: "период не отражён в ИЛС", evidence: "docs" }],
        },
        diag_offer: { allowed: true, amount_rub: 3000 },
      },
    },
  };

  const before = toFunnelFacts({ ...base });
  assert.equal(before.precheck.outcome, "discrepancies");
  assert.equal(before.precheck.summaryDelivery, "not_sent");
  assert.equal(buildFunnel(before).stages.find((s) => s.id === "precheck_summary")?.status, "needs_action");

  const after = toFunnelFacts({
    ...base,
    chat_messages: [
      {
        author_kind: "staff",
        body:
          "Проверили ваши документы. Вот что требует внимания.\n\n1. период\n\nЧто это означает для вас\nЭто краткая сверка по документам.",
      },
    ],
  });
  assert.equal(after.precheck.summaryDelivery, "confirmed");
  assert.equal(buildFunnel(after).stages.find((s) => s.id === "precheck_summary")?.status, "done");

  const byAudit = toFunnelFacts({
    ...base,
    audit: [{ action: "brief_summary_sent" }],
  });
  assert.equal(byAudit.precheck.summaryDelivery, "confirmed");
  assert.equal(buildFunnel(byAudit).stages.find((s) => s.id === "precheck_summary")?.status, "done");
});

test("DIAG paid: этап 3 done, текущий — подробный анализ (не повторная оплата)", () => {
  const facts = toFunnelFacts({
    pipeline_status: "human_review",
    b2c_status: "in_progress",
    consent_accepted: true,
    client: { max_linked: true, phone: "+7900" },
    documents: [
      { doc_type: "ils", storage_path: "c/ils.pdf" },
      { doc_type: "workbook", storage_path: "c/tk.pdf" },
    ],
    orders: [{ package_code: "DIAG", amount_rub: 1, status: "paid" }],
    ordersLoaded: true,
    document_check: {
      status: "completed",
      stale: false,
      result: {
        honest_brief: {
          has_justified_discrepancy: true,
          offer_diag_allowed: true,
          items: [{ text: "период не отражён", evidence: "docs" }],
        },
        diag_offer: { allowed: true, amount_rub: 3000 },
      },
    },
  });
  assert.equal(facts.precheck.summaryDelivery, "confirmed");
  assert.equal(facts.analysis.order.state, "paid");
  const funnel = buildFunnel(facts);
  assert.equal(funnel.stages.find((s) => s.id === "precheck_summary")?.status, "done");
  assert.equal(funnel.stages.find((s) => s.id === "analysis_payment")?.status, "done");
  assert.equal(funnel.currentStageId, "full_analysis");
});

test("маршрут: не хватает документа — current=documents, не прыжок на оплату", () => {
  const facts = toFunnelFacts({
    pipeline_status: "documents_requested",
    b2c_status: "in_progress",
    consent_accepted: true,
    client: { max_linked: true, phone: "+7900" },
    documents: [{ doc_type: "ils", storage_path: "c/ils.pdf" }],
    orders: [],
    ordersLoaded: true,
  });
  assert.equal(facts.documents, "needs_action");
  const funnel = buildFunnel(facts);
  assert.equal(funnel.currentStageId, "documents");
  assert.equal(funnel.priorityStageId ?? null, null);
});

test("маршрут: доп. услуга не требуется — escalation not_required", () => {
  const funnel = buildFunnel({
    ...baseFacts({
      contact: "complete",
      documents: "ready",
      precheck: {
        state: "completed",
        stale: false,
        outcome: "clear",
        summaryDelivery: "confirmed",
      },
      analysis: {
        need: "not_needed",
        order: { state: "not_ordered", entitlement: "none" },
        work: work("not_started"),
      },
      escalation: {
        need: "not_needed",
        consent: "declined",
        order: emptyOrder(),
        work: work(),
      },
      closure: { state: "open" },
    }),
  });
  assert.equal(funnel.stages.find((s) => s.id === "escalation_package")?.status, "not_required");
});

test("priority: ответ СФР при незакрытой цепочке не подменяет current", () => {
  const facts = toFunnelFacts(
    {
      pipeline_status: "submitted",
      b2c_status: "in_progress",
      consent_accepted: true,
      client: { max_linked: true, phone: "+7900" },
      documents: [
        { doc_type: "ils", storage_path: "c/ils.pdf" },
        { doc_type: "workbook", storage_path: "c/tk.pdf" },
      ],
      orders: [{ package_code: "DIAG", amount_rub: 3000, status: "paid" }],
      ordersLoaded: true,
      document_check: {
        status: "completed",
        stale: false,
        result: {
          honest_brief: {
            has_justified_discrepancy: true,
            offer_diag_allowed: true,
            items: [{ text: "x", evidence: "docs" }],
          },
        },
      },
      audit: [{ action: "brief_summary_sent" }],
    },
    {
      submission: "awaiting_client",
      followUp: { state: "active", callRequired: false },
      response: "received",
      escalation: { need: "not_needed" },
    },
  );
  const funnel = buildFunnel(facts);
  // Маршрут — ранний незавершённый (анализ/согласование…), срочно — ответ СФР.
  assert.notEqual(funnel.currentStageId, "response_review");
  assert.equal(funnel.priorityStageId, "response_review");
});

test("preferredStageId задаёт priority, не current", () => {
  const funnel = buildFunnel(
    baseFacts({
      contact: "complete",
      documents: "ready",
      precheck: {
        state: "completed",
        stale: false,
        outcome: "discrepancies",
        summaryDelivery: "confirmed",
      },
      analysis: {
        need: "recommended",
        order: { state: "paid", entitlement: "granted", amountRub: 3000 },
        work: work("not_started"),
      },
      preferredStageId: "response_review",
    }),
  );
  assert.equal(funnel.currentStageId, "full_analysis");
  assert.equal(funnel.priorityStageId, "response_review");
});
