import assert from "node:assert/strict";
import test from "node:test";

import { extractCaseChatDocumentId } from "./case-chat-doc-id.ts";

const DOC_ID = "538c5910-f2ac-4e29-bea8-7be3a62de30e";

test("extracts doc_id at end", () => {
  const body = `[Документ] ils.pdf · Выписка ИЛС · doc_id=${DOC_ID}`;
  const out = extractCaseChatDocumentId(body);
  assert.equal(out.documentId, DOC_ID);
  assert.equal(out.textWithoutDocId, "[Документ] ils.pdf · Выписка ИЛС");
});

test("extracts doc_id when cloud note follows (legacy broken order)", () => {
  const body = `[Документ] scan.pdf · doc_id=${DOC_ID} [нужна догрузка в облако]`;
  const out = extractCaseChatDocumentId(body);
  assert.equal(out.documentId, DOC_ID);
  assert.match(out.textWithoutDocId, /нужна догрузка/);
  assert.doesNotMatch(out.textWithoutDocId, /doc_id=/);
});

test("extracts doc_id when note is before id (canonical)", () => {
  const body = `[Документ] scan.pdf [нужна догрузка в облако] · doc_id=${DOC_ID}`;
  const out = extractCaseChatDocumentId(body);
  assert.equal(out.documentId, DOC_ID);
  assert.equal(
    out.textWithoutDocId,
    "[Документ] scan.pdf [нужна догрузка в облако]",
  );
});

test("no doc_id — open by name forbidden", () => {
  const out = extractCaseChatDocumentId("[Документ] old.pdf · Выписка ИЛС");
  assert.equal(out.documentId, null);
  assert.equal(out.textWithoutDocId, "[Документ] old.pdf · Выписка ИЛС");
});
