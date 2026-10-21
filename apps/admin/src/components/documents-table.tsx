"use client";

import { useMemo, useState } from "react";

export type CabinetDocument = {
  id: string;
  storage_path: string;
  doc_type?: string | null;
  doc_type_label?: string | null;
  created_at?: string;
  filename?: string | null;
  content_preview?: string | null;
  inner_date?: string | null;
  inner_title?: string | null;
  downloadable?: boolean | null;
  ingest_status?: string | null;
  antivirus_status?: string | null;
  mime_verified?: string | null;
  ingest_review_required?: boolean | null;
  progress_message?: string | null;
  has_local_file?: boolean | null;
};

type SortKey = "created_at" | "filename" | "inner_title";
type SortDir = "asc" | "desc";

type Props = {
  documents: CabinetDocument[];
  onOpen: (documentId: string, mode?: "open" | "download") => void;
  busy?: boolean;
  emptyHint?: string;
};

function isPdfDoc(doc: CabinetDocument): boolean {
  const mime = (doc.mime_verified || "").toLowerCase();
  if (mime.startsWith("application/pdf")) return true;
  const name = (doc.filename || doc.storage_path || "").toLowerCase();
  return name.endsWith(".pdf");
}

function isDocx(doc: CabinetDocument): boolean {
  const mime = (doc.mime_verified || "").toLowerCase();
  if (mime.includes("wordprocessingml") || mime.includes("msword")) return true;
  const name = (doc.filename || doc.storage_path || "").toLowerCase();
  return name.endsWith(".docx") || name.endsWith(".doc");
}

function shortName(doc: CabinetDocument): string {
  const raw = (doc.filename || doc.storage_path.split("/").pop() || "документ").trim();
  if (raw.length <= 42) return raw;
  const ext = raw.includes(".") ? raw.slice(raw.lastIndexOf(".")) : "";
  return `${raw.slice(0, 34)}…${ext}`;
}

function formatUploadAt(value?: string) {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return "—";
  return dt.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function receiptLabel(doc: CabinetDocument): string {
  const status = (doc.ingest_status || "").toLowerCase();
  const av = (doc.antivirus_status || "").toLowerCase();
  if (av === "infected" || av === "malicious") return "заблокирован AV";
  if (status === "needs_reupload" && doc.has_local_file) {
    return "на сервере, облако позже";
  }
  if (status === "needs_reupload") return "нужна пересъёмка";
  if (status === "security_check" || status === "quarantine") return "проверка безопасности";
  if (doc.downloadable === false) return "ещё недоступен";
  return formatUploadAt(doc.created_at);
}

function textProcessLabel(doc: CabinetDocument): string {
  const status = (doc.ingest_status || "").toLowerCase();
  const preview = (doc.content_preview || "").trim();
  if (status === "ocr_done" || status === "ready" || status === "classified") {
    return preview ? "текст есть" : "обработан";
  }
  if (status === "ocr_running" || status === "extracting") return "идёт OCR";
  if (status === "manual_review" || doc.ingest_review_required) return "на проверке";
  if (status === "blocked_security") return "стоп: безопасность";
  if (preview) return "превью есть";
  if (doc.progress_message) return doc.progress_message;
  return "текст ещё нет";
}

function needsReview(doc: CabinetDocument): boolean {
  if (doc.ingest_review_required) return true;
  const status = (doc.ingest_status || "").toLowerCase();
  const av = (doc.antivirus_status || "").toLowerCase();
  if (status === "manual_review" || status === "security_check") return true;
  if (av === "pending" || av === "error") return true;
  return false;
}

function blockReason(doc: CabinetDocument): string {
  const av = (doc.antivirus_status || "").toLowerCase();
  if (av === "infected" || av === "malicious") {
    return "Заблокирован антивирусом";
  }
  return "Файл ещё недоступен";
}

function primaryAction(doc: CabinetDocument): {
  kind: "open" | "download" | "blocked" | "wait";
  label: string;
} {
  const canOpen = doc.downloadable !== false;
  if (!canOpen) return { kind: "blocked", label: blockReason(doc) };
  if (isDocx(doc)) return { kind: "download", label: "Скачать" };
  if (isPdfDoc(doc)) return { kind: "open", label: "Открыть оригинал" };
  return { kind: "download", label: "Скачать" };
}

function cellValue(row: CabinetDocument, key: SortKey): string {
  if (key === "created_at") return formatUploadAt(row.created_at);
  if (key === "filename") return shortName(row);
  return (row.inner_title || row.doc_type_label || "Документ").trim();
}

function sortValue(row: CabinetDocument, key: SortKey): string | number {
  if (key === "created_at") {
    const t = row.created_at ? Date.parse(row.created_at) : 0;
    return Number.isNaN(t) ? 0 : t;
  }
  return cellValue(row, key).toLowerCase();
}

export function DocumentsTable({
  documents,
  onOpen,
  busy,
  emptyHint = "Пока файлов нет — клиент ещё не загрузил документы.",
}: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const sorted = useMemo(() => {
    const rows = [...documents];
    rows.sort((a, b) => {
      const av = sortValue(a, sortKey);
      const bv = sortValue(b, sortKey);
      let cmp = 0;
      if (typeof av === "number" && typeof bv === "number") cmp = av - bv;
      else cmp = String(av).localeCompare(String(bv), "ru");
      return sortDir === "asc" ? cmp : -cmp;
    });
    return rows;
  }, [documents, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDir(key === "created_at" ? "desc" : "asc");
  }

  function sortMark(key: SortKey) {
    if (sortKey !== key) return "↕";
    return sortDir === "asc" ? "↑" : "↓";
  }

  return (
    <div className="docs-table-wrap" id="docs-table">
      <div className="docs-table-head">
        <h2>Документы в деле</h2>
        <p className="docs-count">
          Всего: {documents.length}
          {" · "}
          оригинал открывается, если безопасность позволяет — независимо от OCR
        </p>
      </div>
      <div className="docs-table-scroll">
        <table className="docs-table">
          <thead>
            <tr>
              <th scope="col" className="docs-table-num">
                №
              </th>
              <th scope="col">
                <button
                  type="button"
                  className="docs-sort-btn"
                  onClick={() => toggleSort("inner_title")}
                >
                  Тип / имя <span aria-hidden="true">{sortMark("inner_title")}</span>
                </button>
              </th>
              <th scope="col">
                <button
                  type="button"
                  className="docs-sort-btn"
                  onClick={() => toggleSort("created_at")}
                >
                  Получение <span aria-hidden="true">{sortMark("created_at")}</span>
                </button>
              </th>
              <th scope="col">Обработка текста</th>
              <th scope="col">Нужна проверка?</th>
              <th scope="col">Действие</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((doc, index) => {
              const typeLabel =
                (doc.doc_type_label || doc.inner_title || "Документ").trim() || "Документ";
              const preview = (doc.content_preview || "").trim();
              const action = primaryAction(doc);
              const review = needsReview(doc);
              const err =
                (doc.antivirus_status || "").toLowerCase() === "error" ||
                (doc.ingest_status || "").toLowerCase() === "blocked_security"
                  ? doc.progress_message || "Ошибка обработки"
                  : null;
              return (
                <tr key={doc.id}>
                  <td className="docs-table-num">{index + 1}</td>
                  <td>
                    <div>
                      <strong>{typeLabel}</strong>
                    </div>
                    <div className="hint">{shortName(doc)}</div>
                    {err ? (
                      <p className="hint warning-inline" style={{ margin: "0.25rem 0 0" }}>
                        {err}
                      </p>
                    ) : null}
                  </td>
                  <td>{receiptLabel(doc)}</td>
                  <td>
                    <div>{textProcessLabel(doc)}</div>
                    {preview ? (
                      <p className="hint" style={{ margin: "0.25rem 0 0", maxWidth: "22rem" }}>
                        {preview.length > 120 ? `${preview.slice(0, 120)}…` : preview}
                      </p>
                    ) : null}
                  </td>
                  <td>{review ? "да" : "нет"}</td>
                  <td>
                    {action.kind === "blocked" || action.kind === "wait" ? (
                      <span className="hint" title={action.label}>
                        {action.label}
                      </span>
                    ) : (
                      <span className="docs-actions">
                        <button
                          type="button"
                          className="linkish"
                          disabled={busy}
                          title={action.label}
                          aria-label={`${action.label}: ${shortName(doc)}`}
                          onClick={() =>
                            onOpen(doc.id, action.kind === "open" ? "open" : "download")
                          }
                        >
                          {action.label}
                        </button>
                        {action.kind === "open" ? (
                          <button
                            type="button"
                            className="linkish"
                            disabled={busy}
                            title="Скачать файл"
                            aria-label={`Скачать: ${shortName(doc)}`}
                            onClick={() => onOpen(doc.id, "download")}
                          >
                            Скачать
                          </button>
                        ) : null}
                        {preview ? (
                          <span className="hint" title="Текст доступен в превью колонки">
                            · текст в превью
                          </span>
                        ) : null}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
            {sorted.length === 0 ? (
              <tr>
                <td colSpan={6} className="hint">
                  {emptyHint}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
