import assert from "node:assert/strict";
import test from "node:test";
import { docRowView } from "./documents-table-view.ts";

test("фото без текста: одно состояние, без пустой «Проверить текст»", () => {
  const v = docRowView({
    ingest_status: "manual_review",
    ingest_review_required: true,
    antivirus_status: "clean",
    content_preview: "",
    has_extracted_text: false,
  });
  assert.equal(v.state, "текст не извлечён");
  assert.equal(v.canReviewText, false);
  assert.equal(v.warning, null);
});

test("антивирус не завершён: одно предупреждение, без повтора сообщения загрузки", () => {
  const v = docRowView({
    ingest_status: "security_check",
    antivirus_status: "error",
    progress_message: "Файл получен. Специалист завершит проверку безопасности перед обработкой.",
  });
  assert.equal(v.state, "антивирус не завершил проверку");
  assert.match(v.warning ?? "", /подтвердите безопасность/i);
  assert.doesNotMatch(v.warning ?? "", /Файл получен/);
});

test("текст есть, нужна проверка — кнопка доступна", () => {
  const v = docRowView({
    ingest_status: "manual_review",
    antivirus_status: "clean",
    content_preview: "ТРУДОВАЯ КНИЖКА",
  });
  assert.equal(v.state, "нужна проверка текста");
  assert.equal(v.canReviewText, true);
});

test("обычный принятый файл", () => {
  const v = docRowView({ ingest_status: "ocr_done", antivirus_status: "clean", content_preview: "x" });
  assert.equal(v.state, "получен · текст есть");
  assert.equal(v.canReviewText, false);
});
