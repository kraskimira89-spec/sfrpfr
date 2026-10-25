/**
 * Очередь проверки текста файлов: копии одного файла — одна строка,
 * статусы — по-русски, пачкой принимаем только текстовый слой PDF/Word.
 */

export type ReviewDoc = {
  id: string;
  filename?: string | null;
  checksum_sha256?: string | null;
  ingest_status?: string | null;
  antivirus_status?: string | null;
  ingest_review_required?: boolean | null;
  content_preview?: string | null;
  has_local_file?: boolean | null;
  progress_message?: string | null;
  downloadable?: boolean | null;
};

export type ReviewGroup<T extends ReviewDoc = ReviewDoc> = {
  key: string;
  primary: T;
  /** Все копии, включая primary: действия применяются ко всем. */
  copies: T[];
};

const INGEST_LABELS: Record<string, string> = {
  manual_review: "нужна проверка текста",
  needs_reupload: "нужна повторная загрузка",
  security_check: "проверка безопасности",
  quarantine: "проверка безопасности",
  queued: "в очереди",
  pending: "в очереди",
  processing: "обрабатывается",
  running: "обрабатывается",
  ocr_done: "текст принят",
  completed: "текст принят",
  failed: "ошибка обработки",
};

const AV_LABELS: Record<string, string> = {
  clean: "антивирус: чисто",
  not_configured: "антивирус не подключён",
  disabled: "антивирус не подключён",
  pending: "антивирус: идёт проверка",
  error: "антивирус: ошибка проверки",
  infected: "антивирус: угроза",
  malicious: "антивирус: угроза",
};

const SOURCE_LABELS: Record<string, string> = {
  pdf_text: "текстовый слой PDF",
  text_layer: "текстовый слой",
  docx: "Word",
  document: "документ",
  ocr: "распознавание скана",
  vision: "распознавание скана",
  saved_preview: "сохранённый текст",
};

const AV_BLOCKING = new Set(["pending", "error", "infected", "malicious"]);
const TEXT_LAYER_RE = /\.(pdf|docx?|txt|rtf|odt)$/i;
/** Меньше — скорее всего пустой скан или мусор: смотреть глазами. */
const MIN_BULK_TEXT = 200;

export function ingestStatusLabel(doc: Pick<ReviewDoc, "ingest_status" | "has_local_file">): string {
  const status = (doc.ingest_status || "").toLowerCase();
  if (status === "needs_reupload" && doc.has_local_file) return "файл на сервере, облако позже";
  return INGEST_LABELS[status] ?? (status ? "статус обработки неизвестен" : "нет статуса");
}

export function antivirusLabel(av: string | null | undefined): string {
  const key = (av || "").toLowerCase();
  return AV_LABELS[key] ?? "антивирус: нет данных";
}

export function pageSourceLabel(source: string | null | undefined): string {
  const key = (source || "").toLowerCase();
  return SOURCE_LABELS[key] ?? (key ? "источник текста" : "—");
}

function needsReview(doc: ReviewDoc): boolean {
  const status = (doc.ingest_status || "").toLowerCase();
  return Boolean(doc.ingest_review_required) || status === "manual_review";
}

export function groupReviewDocs<T extends ReviewDoc>(docs: T[]): ReviewGroup<T>[] {
  const byKey = new Map<string, T[]>();
  for (const doc of docs) {
    const key = (doc.checksum_sha256 || "").trim() || doc.id;
    const list = byKey.get(key) ?? [];
    list.push(doc);
    byKey.set(key, list);
  }
  return [...byKey.entries()].map(([key, copies]) => ({
    key,
    primary: copies.find((d) => (d.ingest_status || "").toLowerCase() === "manual_review") ?? copies[0],
    copies,
  }));
}

/** Пачкой: PDF/Word с текстом, антивирус не блокирует, есть что принимать. */
export function canBulkAccept(group: ReviewGroup): boolean {
  const name = group.primary.filename || "";
  const text = (group.primary.content_preview || "").trim();
  return (
    TEXT_LAYER_RE.test(name) &&
    text.length >= MIN_BULK_TEXT &&
    group.copies.some(needsReview) &&
    group.copies.every((d) => !AV_BLOCKING.has((d.antivirus_status || "").toLowerCase()))
  );
}

export function reviewSummary(groups: ReviewGroup[]): { files: number; copies: number; bulk: number } {
  return {
    files: groups.length,
    copies: groups.reduce((n, g) => n + g.copies.length, 0),
    bulk: groups.filter(canBulkAccept).length,
  };
}
