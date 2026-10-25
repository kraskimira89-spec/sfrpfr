import assert from "node:assert/strict";
import test from "node:test";

import {
  FUNNEL_STAGE_IDS,
  buildFunnelStages,
  selectCurrentStage,
  type FunnelFacts,
  type OrderFacts,
  type StageActionId,
} from "./case-funnel.ts";
import { deriveFunnel, toFunnelFacts } from "./case-funnel-facts.ts";
import { loaded, unavailable } from "./case-funnel-types.ts";

const ALL_ACTIONS: StageActionId[] = [
  "edit_contacts",
  "request_consents",
  "upload_documents",
  "run_precheck",
  "view_precheck",
  "send_summary",
  "open_analysis_order",
  "prepare_analysis",
  "deliver_analysis",
  "request_appeals_consent",
  "open_appeals_order",
  "prepare_appeals",
  "deliver_appeals",
  "record_submission",
  "request_submission_help",
  "schedule_call",
  "record_follow_up",
  "review_response",
  "open_escalation",
  "review_closure",
  "view_history",
];

function hasAction(stages: ReturnType<typeof buildFunnelStages>, id: string, action: StageActionId) {
  const s = stages.find((x) => x.id === id);
  return Boolean(s?.actions.some((a) => a.id === action && a.enabled));
}

function baseFacts(over: Partial<FunnelFacts> = {}): FunnelFacts {
  const emptyOrder: OrderFacts = { state: "not_ordered", entitlement: "none" };
  const base: FunnelFacts = {
    contacts: { known: true, reachable: true, requiredConsents: "confirmed" },
    documents: {
      known: true,
      count: 2,
      processing: false,
      sufficient: true,
      needsAttention: false,
    },
    precheck: {
      state: "completed",
      stale: false,
      outcome: "discrepancies",
      summaryDelivery: "unknown",
    },
    analysis: {
      recommendation: "recommended",
      order: emptyOrder,
      result: { state: "not_started" },
    },
    appeals: {
      need: "unknown",
      consent: "not_requested",
      order: emptyOrder,
      package: {
        state: "not_started",
        fileCount: 0,
        allReviewed: false,
        clientApproved: false,
      },
    },
    submission: { state: "not_started" },
    followUp: { state: "inactive", callDue: false },
    response: { state: "none" },
    escalation: {
      decision: "unknown",
      consent: "not_requested",
      order: emptyOrder,
      result: { state: "not_started" },
    },
    closure: { state: "open", chronologyReady: false },
    sourceNotes: {},
    permissions: { allowedActions: ALL_ACTIONS },
  };
  return {
    ...base,
    ...over,
    contacts: { ...base.contacts, ...over.contacts },
    documents: { ...base.documents, ...over.documents },
    precheck: { ...base.precheck, ...over.precheck },
    analysis: {
      ...base.analysis,
      ...over.analysis,
      order: { ...base.analysis.order, ...over.analysis?.order },
      result: { ...base.analysis.result, ...over.analysis?.result },
    },
    appeals: {
      ...base.appeals,
      ...over.appeals,
      order: { ...base.appeals.order, ...over.appeals?.order },
      package: { ...base.appeals.package, ...over.appeals?.package },
    },
    escalation: {
      ...base.escalation,
      ...over.escalation,
      order: { ...base.escalation.order, ...over.escalation?.order },
      result: { ...base.escalation.result, ...over.escalation?.result },
    },
    sourceNotes: { ...base.sourceNotes, ...over.sourceNotes },
    permissions: over.permissions ?? base.permissions,
  };
}

test("всегда возвращает 13 уникальных ступеней", () => {
  const stages = buildFunnelStages(baseFacts());
  assert.equal(stages.length, 13);
  assert.deepEqual(
    stages.map((s) => s.id),
    [...FUNNEL_STAGE_IDS],
  );
});

test("не считает неизвестную оплату отсутствием заказа", () => {
  const pay = buildFunnelStages(
    baseFacts({
      analysis: {
        recommendation: "recommended",
        order: { state: "unknown", entitlement: "unknown" },
        result: { state: "not_started" },
      },
    }),
  ).find((s) => s.id === "analysis_payment");
  assert.equal(pay?.status, "unknown");
});

test("не скрывает подтверждённую оплату при изменении рекомендации", () => {
  const pay = buildFunnelStages(
    baseFacts({
      analysis: {
        recommendation: "not_needed",
        order: { state: "paid", entitlement: "granted", amountRub: 3000 },
        result: { state: "not_started" },
      },
      precheck: {
        state: "completed",
        stale: true,
        outcome: "clear",
        summaryDelivery: "unknown",
      },
    }),
  ).find((s) => s.id === "analysis_payment");
  assert.equal(pay?.status, "done");
});

test("не разрешает выдачу анализа без entitlement", () => {
  const full = buildFunnelStages(
    baseFacts({
      analysis: {
        recommendation: "recommended",
        order: { state: "paid", entitlement: "none", amountRub: 3000 },
        result: { state: "ready" },
      },
    }),
  ).find((s) => s.id === "full_analysis");
  assert.equal(full?.status, "blocked");
});

test("не считает готовый результат переданным", () => {
  const stages = buildFunnelStages(
    baseFacts({
      analysis: {
        recommendation: "recommended",
        order: { state: "paid", entitlement: "granted", amountRub: 3000 },
        result: { state: "ready" },
      },
    }),
  );
  assert.ok(hasAction(stages, "full_analysis", "deliver_analysis"));
});

test("не считает queued/running завершённой предпроверкой", () => {
  for (const state of ["queued", "running"] as const) {
    const pre = buildFunnelStages(
      baseFacts({
        precheck: { state, stale: false, outcome: "unknown", summaryDelivery: "unknown" },
      }),
    ).find((s) => s.id === "precheck_summary");
    assert.notEqual(pre?.status, "done");
  }
});

test("помечает устаревшую предпроверку как needs_action", () => {
  const pre = buildFunnelStages(
    baseFacts({
      precheck: {
        state: "completed",
        stale: true,
        outcome: "discrepancies",
        summaryDelivery: "unknown",
      },
    }),
  ).find((s) => s.id === "precheck_summary");
  assert.equal(pre?.status, "needs_action");
  assert.ok(hasAction([pre!], "precheck_summary", "run_precheck") || pre?.actions[0]?.id === "run_precheck");
});

test("не разрешает передачу непроверенного пакета обращений", () => {
  const docs = buildFunnelStages(
    baseFacts({
      analysis: {
        recommendation: "recommended",
        order: { state: "paid", entitlement: "granted" },
        result: { state: "delivered" },
      },
      appeals: {
        need: "recommended",
        consent: "accepted",
        order: { state: "paid", entitlement: "granted", amountRub: 5000 },
        package: {
          state: "ready",
          fileCount: 2,
          allReviewed: false,
          clientApproved: false,
        },
      },
    }),
  ).find((s) => s.id === "appeals_documents");
  assert.equal(docs?.status, "needs_action");
  assert.ok((docs?.blockers || []).length > 0);
});

test("не считает отправку файлов подтверждённой подачей", () => {
  const sub = buildFunnelStages(
    baseFacts({
      analysis: {
        recommendation: "recommended",
        order: { state: "paid", entitlement: "granted" },
        result: { state: "delivered" },
      },
      appeals: {
        need: "recommended",
        consent: "accepted",
        order: { state: "paid", entitlement: "granted" },
        package: {
          state: "delivered",
          fileCount: 1,
          allReviewed: true,
          clientApproved: true,
        },
      },
      submission: { state: "awaiting_client" },
    }),
  ).find((s) => s.id === "submission");
  assert.notEqual(sub?.status, "done");
});

test("не считает оплату дополнительного пакета его завершением", () => {
  const esc = buildFunnelStages(
    baseFacts({
      escalation: {
        decision: "recommended",
        consent: "accepted",
        order: { state: "paid", entitlement: "none", amountRub: 8000 },
        result: { state: "not_started" },
      },
    }),
  ).find((s) => s.id === "escalation_package");
  assert.notEqual(esc?.status, "done");
});

test("не закрывает дело автоматически после последней оплаты", () => {
  const closure = buildFunnelStages(
    baseFacts({
      analysis: {
        recommendation: "recommended",
        order: { state: "paid", entitlement: "granted" },
        result: { state: "delivered" },
      },
      closure: { state: "open", chronologyReady: false },
    }),
  ).find((s) => s.id === "closure");
  assert.notEqual(closure?.status, "done");
});

test("не показывает включённые действия вне allowedActions", () => {
  const docs = buildFunnelStages(
    baseFacts({
      documents: {
        known: true,
        count: 0,
        processing: false,
        sufficient: false,
        needsAttention: false,
      },
      permissions: { allowedActions: ["view_history"] },
    }),
  ).find((s) => s.id === "documents");
  assert.ok(docs?.actions.every((a) => !a.enabled || a.id === "view_history"));
});

test("selectCurrentStage не берёт первый not-done без action", () => {
  const stages = buildFunnelStages(
    baseFacts({
      contacts: { known: true, reachable: false, requiredConsents: "confirmed" },
      documents: {
        known: true,
        count: 0,
        processing: false,
        sufficient: false,
        needsAttention: false,
      },
    }),
  );
  assert.equal(selectCurrentStage(stages), "contact_consents");
});

test("current — не StageStatus: waiting остаётся waiting", () => {
  const stages = buildFunnelStages(
    baseFacts({
      analysis: {
        recommendation: "recommended",
        order: { state: "pending", entitlement: "none", amountRub: 3000 },
        result: { state: "not_started" },
      },
    }),
  );
  const pay = stages.find((s) => s.id === "analysis_payment");
  assert.equal(pay?.status, "waiting");
});

test("sourceNotes unavailable ≠ пустой список ответов", () => {
  const stages = buildFunnelStages(
    baseFacts({
      response: { state: "unknown" },
      sourceNotes: { response_review: "Источник ответов недоступен" },
    }),
  );
  const r = stages.find((s) => s.id === "response_review");
  assert.equal(r?.status, "unknown");
  assert.match(r?.summary || "", /недоступен/i);
});

test("toFunnelFacts: later loaded responses empty → waiting none", () => {
  const facts = toFunnelFacts({
    pipeline_status: "human_review",
    b2c_status: "lead",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [],
    orders: [],
    ordersLoaded: true,
    laterStageFacts: {
      appealsOrder: unavailable("n/a"),
      appealsDocuments: unavailable("n/a"),
      submission: unavailable("n/a"),
      followUp: unavailable("n/a"),
      responses: loaded([]),
      escalation: unavailable("n/a"),
      closure: unavailable("n/a"),
    },
  });
  assert.equal(facts.response.state, "none");
  assert.equal(facts.sourceNotes.response_review, undefined);
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
});
