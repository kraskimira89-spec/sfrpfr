import assert from "node:assert/strict";
import test from "node:test";

import { FUNNEL_STAGE_ORDER, deriveFunnel } from "./case-funnel.ts";

function baseDetail(
  docs: { doc_type?: string | null; storage_path?: string }[],
  extra: Partial<Parameters<typeof deriveFunnel>[0]> = {},
) {
  return {
    pipeline_status: "documents_received",
    b2c_status: "lead",
    consent_accepted: true,
    client: { max_linked: true, web_linked: false },
    documents: docs,
    checklist_items: [] as { title?: string; status?: string; item_type?: string }[],
    ...extra,
  };
}

test("doc_type workbook counts as labor for kit", () => {
  const funnel = deriveFunnel(
    baseDetail([
      { doc_type: "ils", storage_path: "c/ils.pdf" },
      { doc_type: "workbook", storage_path: "c/tk.docx" },
    ]),
  );
  assert.equal(funnel.hasIls, true);
  assert.equal(funnel.hasLabor, true);
  assert.equal(funnel.docsRequiredOk, true);
  assert.deepEqual(funnel.missingDocs, []);
});

test("doc_type labor_book counts as labor", () => {
  const funnel = deriveFunnel(
    baseDetail([{ doc_type: "labor_book", storage_path: "c/a.pdf" }]),
  );
  assert.equal(funnel.hasLabor, true);
});

test("workbook alone does not invent ИЛС", () => {
  const funnel = deriveFunnel(
    baseDetail([{ doc_type: "workbook", storage_path: "c/tk.pdf" }]),
  );
  assert.equal(funnel.hasLabor, true);
  assert.equal(funnel.hasIls, false);
  assert.ok(funnel.missingDocs.some((m) => m.includes("ИЛС")));
});

test("adapter exposes exactly 13 UI stages", () => {
  const funnel = deriveFunnel(baseDetail([]));
  assert.equal(funnel.stages.length, 13);
  assert.deepEqual(
    funnel.stages.map((s) => s.id),
    FUNNEL_STAGE_ORDER,
  );
});

test("incomplete lead stays on contact_consents", () => {
  const funnel = deriveFunnel(
    baseDetail([], {
      consent_accepted: false,
      client: { max_linked: false, web_linked: false },
    }),
  );
  assert.equal(funnel.current, "contact_consents");
});

test("paymentKnown distinguishes none / pending / paid / unknown", () => {
  assert.equal(deriveFunnel(baseDetail([])).paymentKnown, "none");
  assert.equal(
    deriveFunnel(baseDetail([], { orders: [{ status: "pending" }] })).paymentKnown,
    "pending",
  );
  assert.equal(
    deriveFunnel(baseDetail([], { orders: [{ status: "paid" }] })).paymentKnown,
    "paid",
  );
  assert.equal(
    deriveFunnel(baseDetail([], { orders: [{ status: "refunded" }] })).paymentKnown,
    "unknown",
  );
});

test("not_wired stages do not pretend live payments for appeals_payment", () => {
  const funnel = deriveFunnel(
    baseDetail(
      [
        { doc_type: "ils", storage_path: "a.pdf" },
        { doc_type: "workbook", storage_path: "b.pdf" },
      ],
      {
        b2c_status: "package_delivered",
        orders: [{ status: "paid" }],
        analysis_notes: "x",
      },
    ),
  );
  const appealsPay = funnel.stages.find((s) => s.id === "appeals_payment");
  assert.ok(appealsPay);
  assert.equal(appealsPay.capability, "not_wired");
  assert.match(appealsPay.shortSummary, /не подключена/i);
});

test("empty document_check does not invent paid analysis", () => {
  const funnel = deriveFunnel(baseDetail([{ doc_type: "ils", storage_path: "a.pdf" }]));
  assert.notEqual(funnel.paymentKnown, "paid");
});
