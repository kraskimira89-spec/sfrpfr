import assert from "node:assert/strict";
import test from "node:test";

import {
  STAGE_IDS,
  buildFunnelStages,
  selectCurrentStage,
  type FunnelFacts,
  type OrderFacts,
} from "./case-funnel.ts";
import { deriveFunnel, toFunnelFacts } from "./case-funnel-facts.ts";

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
    permissions: {
      allowedActions: [
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
      ],
    },
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
    permissions: over.permissions ?? base.permissions,
  };
}

test("всегда возвращает 13 уникальных ступеней", () => {
  const stages = buildFunnelStages(baseFacts());
  assert.equal(stages.length, 13);
  assert.deepEqual(
    stages.map((s) => s.id),
    [...STAGE_IDS],
  );
  assert.equal(new Set(stages.map((s) => s.id)).size, 13);
});

test("не считает неизвестную оплату отсутствием заказа", () => {
  const stages = buildFunnelStages(
    baseFacts({
      analysis: {
        recommendation: "recommended",
        order: { state: "unknown", entitlement: "unknown" },
        result: { state: "not_started" },
      },
    }),
  );
  const pay = stages.find((s) => s.id === "analysis_payment");
  assert.equal(pay?.status, "unknown");
  assert.match(pay?.summary || "", /недоступен|не удалось/i);
});

test("не скрывает подтверждённую оплату при изменении рекомендации", () => {
  const stages = buildFunnelStages(
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
  );
  const pay = stages.find((s) => s.id === "analysis_payment");
  assert.equal(pay?.status, "done");
  assert.match(pay?.title || "", /3/);
});

test("не разрешает выдачу анализа без entitlement", () => {
  const stages = buildFunnelStages(
    baseFacts({
      analysis: {
        recommendation: "recommended",
        order: { state: "paid", entitlement: "none", amountRub: 3000 },
        result: { state: "ready" },
      },
    }),
  );
  const full = stages.find((s) => s.id === "full_analysis");
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
  const full = stages.find((s) => s.id === "full_analysis");
  assert.equal(full?.status, "needs_action");
  assert.equal(full?.action, "deliver_analysis");
});

test("не считает queued/running завершённой предпроверкой", () => {
  for (const state of ["queued", "running"] as const) {
    const stages = buildFunnelStages(
      baseFacts({
        precheck: {
          state,
          stale: false,
          outcome: "unknown",
          summaryDelivery: "unknown",
        },
      }),
    );
    const pre = stages.find((s) => s.id === "precheck_summary");
    assert.notEqual(pre?.status, "done");
    assert.ok(["waiting", "in_progress"].includes(pre?.status || ""));
  }
});

test("помечает устаревшую предпроверку как needs_action", () => {
  const stages = buildFunnelStages(
    baseFacts({
      precheck: {
        state: "completed",
        stale: true,
        outcome: "discrepancies",
        summaryDelivery: "unknown",
      },
    }),
  );
  const pre = stages.find((s) => s.id === "precheck_summary");
  assert.equal(pre?.status, "needs_action");
  assert.equal(pre?.action, "run_precheck");
});

test("не разрешает передачу непроверенного пакета обращений", () => {
  const stages = buildFunnelStages(
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
  );
  const docs = stages.find((s) => s.id === "appeals_documents");
  assert.equal(docs?.status, "needs_action");
  assert.ok((docs?.blockers || []).length > 0);
});

test("не считает отправку файлов подтверждённой подачей", () => {
  const stages = buildFunnelStages(
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
  );
  const sub = stages.find((s) => s.id === "submission");
  assert.notEqual(sub?.status, "done");
});

test("не считает оплату дополнительного пакета его завершением", () => {
  const stages = buildFunnelStages(
    baseFacts({
      escalation: {
        decision: "recommended",
        consent: "accepted",
        order: { state: "paid", entitlement: "none", amountRub: 8000 },
        result: { state: "not_started" },
      },
    }),
  );
  const esc = stages.find((s) => s.id === "escalation_package");
  assert.notEqual(esc?.status, "done");
  assert.match(esc?.summary || "", /Оплата есть|сверить/i);
});

test("не закрывает дело автоматически после последней оплаты", () => {
  const stages = buildFunnelStages(
    baseFacts({
      analysis: {
        recommendation: "recommended",
        order: { state: "paid", entitlement: "granted" },
        result: { state: "delivered" },
      },
      closure: { state: "open", chronologyReady: false },
    }),
  );
  const closure = stages.find((s) => s.id === "closure");
  assert.notEqual(closure?.status, "done");
});

test("не показывает действия, отсутствующие в allowedActions", () => {
  const stages = buildFunnelStages(
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
  );
  const docs = stages.find((s) => s.id === "documents");
  assert.equal(docs?.action, undefined);
});

test("selectCurrentStage предпочитает needs_action с action, не первый not done", () => {
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
  const cur = selectCurrentStage(stages);
  assert.equal(cur, "contact_consents");
});

test("toFunnelFacts: unknown order load ≠ not_ordered", () => {
  const facts = toFunnelFacts({
    pipeline_status: "human_review",
    b2c_status: "lead",
    consent_accepted: true,
    client: { max_linked: true, web_linked: false },
    documents: [],
    orders: undefined,
    ordersLoaded: false,
  });
  assert.equal(facts.analysis.order.state, "unknown");
});

test("toFunnelFacts: пустой orders при loaded → not_ordered", () => {
  const facts = toFunnelFacts({
    pipeline_status: "documents_received",
    b2c_status: "lead",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [{ doc_type: "ils" }, { doc_type: "workbook" }],
    orders: [],
    ordersLoaded: true,
  });
  assert.equal(facts.analysis.order.state, "not_ordered");
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
  assert.equal(facts.analysis.order.entitlement, "none");
});

test("toFunnelFacts: DIAG paid → entitlement granted; draft ≠ delivered appeals", () => {
  const facts = toFunnelFacts({
    pipeline_status: "human_review",
    b2c_status: "new",
    consent_accepted: true,
    client: { max_linked: true },
    documents: [{ doc_type: "diagnosis_report", storage_path: "x.pdf" }],
    draft: { title: "t", body: "b" },
    orders: [{ package_code: "DIAG", status: "paid", amount_rub: 3000 }],
    ordersLoaded: true,
    audit: [],
  });
  assert.equal(facts.analysis.order.state, "paid");
  assert.equal(facts.analysis.order.entitlement, "granted");
  assert.equal(facts.analysis.result.state, "ready");
  assert.notEqual(facts.appeals.package.state, "delivered");
});

test("deriveFunnel kit workbook / ИЛС", () => {
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
  assert.equal(funnel.hasLabor, true);
  assert.equal(funnel.stages.length, 13);
});
