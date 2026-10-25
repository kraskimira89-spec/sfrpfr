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
  assert.equal(facts.submission, "unknown");
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
