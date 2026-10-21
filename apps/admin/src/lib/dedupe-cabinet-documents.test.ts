import assert from "node:assert/strict";
import test from "node:test";

import { dedupeCabinetDocuments } from "./dedupe-cabinet-documents.ts";

test("dedupe by checksum keeps one of identical bytes", () => {
  const rows = dedupeCabinetDocuments([
    { id: "a", checksum_sha256: "same", created_at: "2026-10-20T10:00:00Z" },
    { id: "b", checksum_sha256: "same", created_at: "2026-10-21T10:00:00Z" },
  ]);
  assert.equal(rows.length, 1);
  assert.equal(rows[0]?.id, "b");
});

test("different checksums stay as separate rows", () => {
  const rows = dedupeCabinetDocuments([
    { id: "p1", checksum_sha256: "aaa", filename: "page1.pdf" },
    { id: "p2", checksum_sha256: "bbb", filename: "page2.pdf" },
  ]);
  assert.equal(rows.length, 2);
});

test("without checksum falls back to id (no false merge by name)", () => {
  const rows = dedupeCabinetDocuments([
    { id: "1", filename: "scan.pdf" },
    { id: "2", filename: "scan.pdf" },
  ]);
  assert.equal(rows.length, 2);
});
