import assert from "node:assert/strict";
import test from "node:test";

import {
  dedupeCabinetDocuments,
  groupCabinetDocumentsByChecksum,
} from "./dedupe-cabinet-documents.ts";

test("dedupe by checksum keeps one of identical bytes", () => {
  const rows = dedupeCabinetDocuments([
    { id: "a", checksum_sha256: "same", created_at: "2026-10-20T10:00:00Z" },
    { id: "b", checksum_sha256: "same", created_at: "2026-10-21T10:00:00Z" },
  ]);
  assert.equal(rows.length, 1);
  assert.equal(rows[0]?.id, "b");
});

test("group keeps history of exact checksum repeats", () => {
  const groups = groupCabinetDocumentsByChecksum([
    { id: "a", checksum_sha256: "same", created_at: "2026-10-20T10:00:00Z" },
    { id: "b", checksum_sha256: "same", created_at: "2026-10-21T10:00:00Z" },
    { id: "c", checksum_sha256: "same", created_at: "2026-10-19T10:00:00Z" },
  ]);
  assert.equal(groups.length, 1);
  assert.equal(groups[0]?.primary.id, "b");
  assert.deepEqual(
    groups[0]?.duplicates.map((d) => d.id),
    ["a", "c"],
  );
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

test("same filename different checksums are not merged", () => {
  const groups = groupCabinetDocumentsByChecksum([
    { id: "1", checksum_sha256: "aaa", filename: "scan.pdf" },
    { id: "2", checksum_sha256: "bbb", filename: "scan.pdf" },
  ]);
  assert.equal(groups.length, 2);
  assert.equal(groups.every((g) => g.duplicates.length === 0), true);
});
