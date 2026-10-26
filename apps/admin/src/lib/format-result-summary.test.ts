import assert from "node:assert/strict";
import test from "node:test";

import {
  formatResultSummaryBrief,
  formatResultSummaryFull,
  sortDocsChronology,
} from "./format-result-summary.ts";

test("brief: как было / как стало", () => {
  const text = formatResultSummaryBrief({
    beforeRub: 10000,
    afterRub: 12500,
    lumpRub: 5000,
    documents: [{ filename: "ils.pdf", created_at: "2024-01-01T00:00:00Z" }],
  });
  assert.match(text, /Как было/);
  assert.match(text, /10[\s\u00a0]?000/);
  assert.match(text, /Как стало/);
  assert.match(text, /Единовременно/);
  assert.match(text, /документов: 1/);
  assert.match(text, /Решение принимает СФР/);
});

test("full: хронология по датам", () => {
  const docs = sortDocsChronology([
    { filename: "b.pdf", created_at: "2025-06-01T00:00:00Z", doc_type: "ils" },
    { filename: "a.pdf", created_at: "2024-01-01T00:00:00Z", doc_type: "workbook" },
  ]);
  assert.equal(docs[0]?.filename, "a.pdf");
  const full = formatResultSummaryFull({
    beforeRub: "8000",
    afterRub: "9000",
    documents: docs,
    caseRef: "case-1",
  });
  assert.match(full, /Хронология документов \(2\)/);
  assert.match(full, /a\.pdf/);
  assert.match(full, /b\.pdf/);
});
