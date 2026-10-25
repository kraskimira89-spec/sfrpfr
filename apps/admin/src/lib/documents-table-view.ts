/**
 * Строка таблицы файлов: одно состояние, одно предупреждение, без повторов.
 * «Проверить текст» — только если текст есть (иначе пустая панель).
 */

export type DocRowInput = {
  ingest_status?: string | null;
  antivirus_status?: string | null;
  ingest_review_required?: boolean | null;
  content_preview?: string | null;
  has_extracted_text?: boolean | null;
  has_local_file?: boolean | null;
  downloadable?: boolean | null;
  progress_message?: string | null;
};

export type DocRowView = {
  state: string;
  canReviewText: boolean;
  warning: string | null;
};

const AV_BLOCKED = new Set(["infected", "malicious"]);
const AV_UNVERIFIED = new Set(["error", "pending"]);

export function docRowView(doc: DocRowInput): DocRowView {
  const av = (doc.antivirus_status || "").toLowerCase();
  const status = (doc.ingest_status || "").toLowerCase();
  const hasText = Boolean((doc.content_preview || "").trim()) || Boolean(doc.has_extracted_text);
  const needsReview = status === "manual_review" || Boolean(doc.ingest_review_required);

  if (AV_BLOCKED.has(av)) {
    return { state: "заблокирован антивирусом", canReviewText: false, warning: null };
  }
  if (AV_UNVERIFIED.has(av)) {
    return {
      state: "антивирус не завершил проверку",
      canReviewText: false,
      warning:
        "⚠ Файл пока не считается безопасным — подтвердите безопасность в «Проверке текста файлов».",
    };
  }
  if (status === "needs_reupload") {
    return {
      state: doc.has_local_file ? "на сервере, облако позже" : "нужна пересъёмка",
      canReviewText: false,
      warning: null,
    };
  }
  if (status === "security_check" || status === "quarantine") {
    return { state: "проверка безопасности", canReviewText: false, warning: null };
  }
  if (needsReview) {
    return hasText
      ? { state: "нужна проверка текста", canReviewText: true, warning: null }
      : { state: "текст не извлечён", canReviewText: false, warning: null };
  }
  if ((doc.content_preview || "").trim()) {
    return { state: "получен · текст есть", canReviewText: false, warning: null };
  }
  if (doc.has_extracted_text) {
    return { state: "получен · текст сохранён отдельно", canReviewText: false, warning: null };
  }
  if (doc.downloadable === false) {
    return { state: "ещё недоступен", canReviewText: false, warning: null };
  }
  return { state: "получен · текста нет", canReviewText: false, warning: null };
}
