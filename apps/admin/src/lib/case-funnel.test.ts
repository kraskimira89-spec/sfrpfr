import assert from "node:assert/strict";
import test from "node:test";

import { deriveFunnel } from "./case-funnel.ts";

function baseDetail(
  docs: { doc_type?: string | null; storage_path?: string }[],
) {
  return {
    pipeline_status: "documents_received",
    b2c_status: "lead",
    consent_accepted: true,
    client: { max_linked: true, web_linked: false },
    documents: docs,
    checklist_items: [] as { title?: string; status?: string; item_type?: string }[],
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
