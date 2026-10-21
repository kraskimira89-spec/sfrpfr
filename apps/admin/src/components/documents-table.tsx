"use client";

import { useMemo, useState } from "react";

import { dedupeCabinetDocuments } from "../lib/dedupe-cabinet-documents";

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
  checksum_sha256?: string | null;
};

type Props = {
  documents: CabinetDocument[];
  onOpen: (documentId: string, mode?: "open" | "download") => void;
  busy?: boolean;
  emptyHint?: string;
};

const AV_UNVERIFIED = new Set(["error", "pending"]);
const AV_BLOCKED = new Set(["infected", "malicious"]);

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
  if (raw.length <= 48) return raw;
  const ext = raw.includes(".") ? raw.slice(raw.lastIndexOf(".")) : "";
  return `${raw.slice(0, 40)}…${ext}`;
}

function needsTextReview(doc: CabinetDocument): boolean {
  const status = (doc.ingest_status || "").toLowerCase();
  return status === "manual_review" || Boolean(doc.ingest_review_required);
}

function stateLabel(doc: CabinetDocument): string {
  const av = (doc.antivirus_status || "").toLowerCase();
  const status = (doc.ingest_status || "").toLowerCase();
  if (AV_BLOCKED.has(av)) return "заблокирован AV";
  if (AV_UNVERIFIED.has(av)) return "AV не завершена (не безопасен)";
  if (status === "needs_reupload" && doc.has_local_file) {
    return "на сервере, облако позже";
  }
  if (status === "needs_reupload") return "нужна пересъёмка";
  if (status === "security_check" || status === "quarantine") return "проверка безопасности";
  if (needsTextReview(doc)) return "нужна проверка текста";
  if ((doc.content_preview || "").trim()) return "получен · текст есть";
  if (doc.downloadable === false) return "ещё недоступен";
  return "получен";
}

function canOpenOriginal(doc: CabinetDocument): boolean {
  return doc.downloadable !== false && !AV_BLOCKED.has((doc.antivirus_status || "").toLowerCase());
}

export function DocumentsTable({
  documents,
  onOpen,
  busy,
  emptyHint = "Пока файлов нет — клиент ещё не загрузил документы.",
}: Props) {
  const [textOpenId, setTextOpenId] = useState<string | null>(null);

  const unique = useMemo(() => dedupeCabinetDocuments(documents), [documents]);

  const sorted = useMemo(() => {
    const rows = [...unique];
    rows.sort((a, b) => {
      const at = a.created_at ? Date.parse(a.created_at) : 0;
      const bt = b.created_at ? Date.parse(b.created_at) : 0;
      return (Number.isNaN(bt) ? 0 : bt) - (Number.isNaN(at) ? 0 : at);
    });
    return rows;
  }, [unique]);

  function toggleText(docId: string) {
    setTextOpenId((cur) => (cur === docId ? null : docId));
  }

  return (
    <div className="docs-table-wrap" id="docs-table">
      <div className="docs-table-head">
        <h2>Документы в деле</h2>
        <p className="docs-count">
          Всего: {unique.length}
          {unique.length !== documents.length
            ? ` · без дублей (было ${documents.length})`
            : ""}
          {" · "}
          Оригинал — preview PDF; Скачать — отдельно; Текст — извлечённый preview
        </p>
      </div>
      <div className="docs-table-scroll">
        <table className="docs-table">
          <thead>
            <tr>
              <th scope="col" className="docs-table-num">
                №
              </th>
              <th scope="col">Тип / имя</th>
              <th scope="col">Состояние</th>
              <th scope="col">Действия</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((doc, index) => {
              const typeLabel =
                (doc.doc_type_label || doc.inner_title || "Документ").trim() || "Документ";
              const preview = (doc.content_preview || "").trim();
              const av = (doc.antivirus_status || "").toLowerCase();
              const unverified = AV_UNVERIFIED.has(av);
              const openOk = canOpenOriginal(doc);
              const pdf = isPdfDoc(doc);
              const word = isDocx(doc);
              const openMode = word || !pdf ? "download" : "open";
              const textOpen = textOpenId === doc.id;
              return (
                <tr key={doc.id} id={textOpen ? `doc-text-${doc.id}` : undefined}>
                  <td className="docs-table-num">{index + 1}</td>
                  <td>
                    <div>
                      <strong>{typeLabel}</strong>
                    </div>
                    <div className="hint">{shortName(doc)}</div>
                    {unverified ? (
                      <p className="hint warning-inline" style={{ margin: "0.25rem 0 0" }}>
                        ⚠ Проверка антивирусом не завершена — файл не считается безопасным
                      </p>
                    ) : null}
                    {doc.progress_message && av === "error" ? (
                      <p className="hint" style={{ margin: "0.25rem 0 0" }}>
                        {doc.progress_message}
                      </p>
                    ) : null}
                  </td>
                  <td>
                    {needsTextReview(doc) ? (
                      <button
                        type="button"
                        className="linkish"
                        disabled={busy || !preview}
                        title={
                          preview
                            ? "Открыть извлечённый текст для проверки"
                            : "Текст ещё не извлечён"
                        }
                        aria-label={`Проверить текст: ${shortName(doc)}`}
                        onClick={() => {
                          if (!preview) return;
                          toggleText(doc.id);
                          requestAnimationFrame(() => {
                            document
                              .getElementById(`doc-text-${doc.id}`)
                              ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
                          });
                        }}
                      >
                        Проверить текст
                      </button>
                    ) : (
                      stateLabel(doc)
                    )}
                  </td>
                  <td>
                    {openOk ? (
                      <span className="docs-actions">
                        <button
                          type="button"
                          className="linkish"
                          disabled={busy}
                          title={
                            unverified
                              ? "AV не завершена: открыть оригинал осторожно"
                              : word
                                ? "Скачать Word"
                                : pdf
                                  ? "Открыть PDF в новой вкладке"
                                  : "Открыть оригинал"
                          }
                          aria-label={`Оригинал: ${shortName(doc)}`}
                          onClick={() => onOpen(doc.id, openMode)}
                        >
                          Оригинал
                        </button>
                        {pdf ? (
                          <button
                            type="button"
                            className="linkish"
                            disabled={busy}
                            title="Скачать PDF"
                            aria-label={`Скачать: ${shortName(doc)}`}
                            onClick={() => onOpen(doc.id, "download")}
                          >
                            Скачать
                          </button>
                        ) : null}
                        {preview ? (
                          <button
                            type="button"
                            className="linkish"
                            disabled={busy}
                            aria-label={`Текст: ${shortName(doc)}`}
                            onClick={() => toggleText(doc.id)}
                          >
                            {textOpen ? "Скрыть текст" : "Текст"}
                          </button>
                        ) : (
                          <span className="hint" title="Нет извлечённого preview">
                            Текст недоступен
                          </span>
                        )}
                      </span>
                    ) : (
                      <span className="hint">
                        {AV_BLOCKED.has(av) ? "Заблокирован антивирусом" : "Файл ещё недоступен"}
                      </span>
                    )}
                    {textOpen && preview ? (
                      <pre
                        className="draft"
                        style={{
                          marginTop: "0.5rem",
                          maxHeight: "12rem",
                          overflow: "auto",
                          whiteSpace: "pre-wrap",
                        }}
                      >
                        {preview.length > 4000 ? `${preview.slice(0, 4000)}…` : preview}
                      </pre>
                    ) : null}
                  </td>
                </tr>
              );
            })}
            {sorted.length === 0 ? (
              <tr>
                <td colSpan={4} className="hint">
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
