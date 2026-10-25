import assert from "node:assert/strict";
import test from "node:test";
import {
  antivirusLabel,
  canBulkAccept,
  groupReviewDocs,
  ingestStatusLabel,
  pageSourceLabel,
  reviewSummary,
} from "./ingest-review-view.ts";

const LONG = "Трудовая книжка, сведения о работе. ".repeat(20);

// Форма очереди дела ПС-600855: копии одного файла с одинаковым checksum.
const DOCS = [
  { id: "t1", filename: "ТК.docx", checksum_sha256: "tk", ingest_status: "manual_review", antivirus_status: "clean", ingest_review_required: true, content_preview: LONG },
  { id: "t2", filename: "ТК.docx", checksum_sha256: "tk", ingest_status: "needs_reupload", antivirus_status: "not_configured", ingest_review_required: true, has_local_file: true, content_preview: LONG },
  { id: "i1", filename: "ИЛС.pdf", checksum_sha256: "ils", ingest_status: "manual_review", antivirus_status: "clean", ingest_review_required: true, content_preview: LONG },
  { id: "p1", filename: "фото.png", checksum_sha256: "png", ingest_status: "manual_review", antivirus_status: "clean", ingest_review_required: true, content_preview: "" },
];

test("копии одного файла склеиваются, основной — на проверке", () => {
  const groups = groupReviewDocs(DOCS);
  assert.equal(groups.length, 3);
  const tk = groups.find((g) => g.key === "tk")!;
  assert.equal(tk.copies.length, 2);
  assert.equal(tk.primary.id, "t1");
});

test("пачкой — только PDF/Word с текстом; фото без текста — вручную", () => {
  const groups = groupReviewDocs(DOCS);
  assert.equal(canBulkAccept(groups.find((g) => g.key === "tk")!), true);
  assert.equal(canBulkAccept(groups.find((g) => g.key === "ils")!), true);
  assert.equal(canBulkAccept(groups.find((g) => g.key === "png")!), false);
});

test("антивирус не завершён — пачкой нельзя", () => {
  const [g] = groupReviewDocs([{ ...DOCS[2], antivirus_status: "pending" }]);
  assert.equal(canBulkAccept(g), false);
});

test("сводка: файлы, копии, можно принять пачкой", () => {
  assert.deepEqual(reviewSummary(groupReviewDocs(DOCS)), { files: 3, copies: 4, bulk: 2 });
});

test("статусы — по-русски", () => {
  assert.equal(ingestStatusLabel(DOCS[0]), "нужна проверка текста");
  assert.equal(ingestStatusLabel(DOCS[1]), "файл на сервере, облако позже");
  assert.equal(ingestStatusLabel({ ingest_status: "security_check" }), "проверка безопасности");
  assert.equal(antivirusLabel("clean"), "антивирус: чисто");
  assert.equal(antivirusLabel("not_configured"), "антивирус не подключён");
  assert.equal(pageSourceLabel("ocr"), "распознавание скана");
  assert.equal(pageSourceLabel("saved_preview"), "сохранённый текст");
});
