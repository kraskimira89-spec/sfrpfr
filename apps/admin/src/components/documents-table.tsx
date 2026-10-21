"use client";

import { useMemo, useState } from "react";

import { groupCabinetDocumentsByChecksum } from "../lib/dedupe-cabinet-documents";

export type CabinetDocument = {
  id: string;
  storage_path: string;
  doc_type?: string | null;
  doc_type_label?: string | null;
  created_at?: string;
  filename?: string | null;
  /** Полный извлечённый текст (до лимита БД). Не путать с кратким описанием. */
  content_preview?: string | null;
  /** Короткий сниппет для подписи «Краткое описание». */
  content_summary?: string | null;
  has_extracted_text?: boolean | null;
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
  if (doc.has_extracted_text) return "получен · текст в артефакте";
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
  const [dupOpenId, setDupOpenId] = useState<string | null>(null);

  const groups = useMemo(
    () => groupCabinetDocumentsByChecksum(documents),
    [documents],
  );
  const hiddenDupCount = documents.length - groups.length;

  function toggleText(docId: string) {
    setTextOpenId((cur) => (cur === docId ? null : docId));
  }

  function toggleDupHistory(docId: string) {
    setDupOpenId((cur) => (cur === docId ? null : docId));
  }

  function formatWhen(iso?: string) {
    if (!iso) return "—";
    const t = Date.parse(iso);
    if (Number.isNaN(t)) return iso;
    return new Date(t).toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  return (
    <div className="docs-table-wrap" id="docs-table">
      <div className="docs-table-head">
        <h2>Документы в деле</h2>
        <p className="docs-count">
          Всего: {groups.length}
          {hiddenDupCount > 0 ? ` · точных дублей скрыто в истории: ${hiddenDupCount}` : ""}
          {" · "}
          PDF: Открыть (preview) · Скачать · Текст; Word: Скачать · Текст
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
            {groups.map((group, index) => {
              const doc = group.primary;
              const dupOpen = dupOpenId === doc.id;
              const typeLabel =
                (doc.doc_type_label || doc.inner_title || "Документ").trim() || "Документ";
              const fullText = (doc.content_preview || "").trim();
              const summary = (doc.content_summary || "").trim();
              const hasFullText = Boolean(fullText);
              const textMissingHonest = !hasFullText
                ? doc.has_extracted_text
                  ? "полный текст в артефакте ingest — preview в карточке пуст"
                  : "текст ещё не извлечён"
                : null;
              const reviewReason = (doc.progress_message || "").trim();
              const av = (doc.antivirus_status || "").toLowerCase();
              const unverified = AV_UNVERIFIED.has(av);
              const openOk = canOpenOriginal(doc);
              const pdf = isPdfDoc(doc);
              const word = isDocx(doc);
              const textOpen = textOpenId === doc.id;

              /** Только панель текста — без open/download (не дублировать «Текст»/скачивание). */
              function openTextReview() {
                setTextOpenId(doc.id);
                requestAnimationFrame(() => {
                  document
                    .getElementById(`doc-text-${doc.id}`)
                    ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
                });
              }

              return (
                <tr key={doc.id} id={textOpen ? `doc-text-${doc.id}` : undefined}>
                  <td className="docs-table-num">{index + 1}</td>
                  <td>
                    <div>
                      <strong>{typeLabel}</strong>
                    </div>
                    <div className="hint">{shortName(doc)}</div>
                    {group.duplicates.length > 0 ? (
                      <div style={{ marginTop: "0.25rem" }}>
                        <button
                          type="button"
                          className="linkish"
                          disabled={busy}
                          onClick={() => toggleDupHistory(doc.id)}
                          aria-expanded={dupOpen}
                        >
                          {dupOpen
                            ? "Скрыть историю повторов"
                            : `Точный дубль · ещё ${group.duplicates.length}`}
                        </button>
                        {dupOpen ? (
                          <ul className="hint" style={{ margin: "0.35rem 0 0", paddingLeft: "1.1rem" }}>
                            {group.duplicates.map((dup) => (
                              <li key={dup.id}>
                                {shortName(dup)} · {formatWhen(dup.created_at)}
                                {canOpenOriginal(dup) ? (
                                  <>
                                    {" · "}
                                    <button
                                      type="button"
                                      className="linkish"
                                      disabled={busy}
                                      onClick={() =>
                                        onOpen(
                                          dup.id,
                                          isPdfDoc(dup) ? "open" : "download",
                                        )
                                      }
                                      onDoubleClick={(e) => e.preventDefault()}
                                    >
                                      {isPdfDoc(dup) ? "открыть" : "скачать"}
                                    </button>
                                  </>
                                ) : null}
                              </li>
                            ))}
                          </ul>
                        ) : null}
                      </div>
                    ) : null}
                    {summary ? (
                      <p className="hint" style={{ margin: "0.25rem 0 0" }}>
                        <strong>Краткое описание.</strong> {summary}
                      </p>
                    ) : null}
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
                        disabled={busy}
                        title={
                          hasFullText
                            ? "Показать полный текст для проверки (без скачивания)"
                            : "Текст ещё не извлечён"
                        }
                        aria-label={`Проверить текст: ${shortName(doc)}`}
                        onClick={() => openTextReview()}
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
                        {pdf ? (
                          <button
                            type="button"
                            className="linkish"
                            disabled={busy}
                            title={
                              unverified
                                ? "AV не завершена: открыть PDF осторожно (только preview)"
                                : "Открыть PDF в новой вкладке (inline, без скачивания)"
                            }
                            aria-label={`Открыть: ${shortName(doc)}`}
                            onClick={() => onOpen(doc.id, "open")}
                            onDoubleClick={(e) => e.preventDefault()}
                          >
                            Открыть
                          </button>
                        ) : null}
                        <button
                          type="button"
                          className="linkish"
                          disabled={busy}
                          title={
                            word
                              ? "Скачать Word"
                              : pdf
                                ? "Скачать PDF (attachment)"
                                : "Скачать файл"
                          }
                          aria-label={`Скачать: ${shortName(doc)}`}
                          onClick={() => onOpen(doc.id, "download")}
                        >
                          Скачать
                        </button>
                        {hasFullText ? (
                          // При review CTA только в «Состояние» — не дублировать «Текст» рядом.
                          needsTextReview(doc) && !textOpen ? null : (
                            <button
                              type="button"
                              className="linkish"
                              disabled={busy}
                              aria-label={`Текст: ${shortName(doc)}`}
                              onClick={() => toggleText(doc.id)}
                            >
                              {textOpen ? "Скрыть" : "Текст"}
                            </button>
                          )
                        ) : (
                          <span className="hint" title={textMissingHonest || "Нет извлечённого текста"}>
                            {textMissingHonest || "Текст недоступен"}
                          </span>
                        )}
                      </span>
                    ) : (
                      <span className="hint">
                        {AV_BLOCKED.has(av) ? "Заблокирован антивирусом" : "Файл ещё недоступен"}
                      </span>
                    )}
                    {textOpen ? (
                      <div className="docs-text-panel" style={{ marginTop: "0.5rem" }}>
                        {reviewReason ? (
                          <p className="hint" style={{ margin: "0 0 0.35rem" }}>
                            Причина проверки: {reviewReason}
                          </p>
                        ) : null}
                        {hasFullText ? (
                          <pre
                            className="draft"
                            style={{
                              margin: 0,
                              maxHeight: "16rem",
                              overflow: "auto",
                              whiteSpace: "pre-wrap",
                            }}
                          >
                            {fullText}
                          </pre>
                        ) : (
                          <p className="hint" style={{ margin: 0 }}>
                            {textMissingHonest || "Полный текст отсутствует — краткое описание вместо текста не показываем."}
                          </p>
                        )}
                      </div>
                    ) : null}
                  </td>
                </tr>
              );
            })}
            {groups.length === 0 ? (
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
