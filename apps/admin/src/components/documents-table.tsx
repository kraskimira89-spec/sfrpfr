"use client";

import { useMemo, useState } from "react";

import { groupCabinetDocumentsByChecksum } from "../lib/dedupe-cabinet-documents";
import { docRowView } from "../lib/documents-table-view";

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
  /** Удалить файлы (эксперт/админ); label — для подтверждения. */
  onDelete?: (documentIds: string[], label: string) => void;
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

function canOpenOriginal(doc: CabinetDocument): boolean {
  return doc.downloadable !== false && !AV_BLOCKED.has((doc.antivirus_status || "").toLowerCase());
}

export function DocumentsTable({
  documents,
  onOpen,
  busy,
  emptyHint = "Пока файлов нет — клиент ещё не загрузил документы.",
  onDelete,
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
        <p className="docs-count">
          Файлов: {groups.length}
          {hiddenDupCount > 0 ? ` · повторных загрузок свёрнуто: ${hiddenDupCount}` : ""}
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
              const row = docRowView(doc);
              const reviewReason = (doc.progress_message || "").trim();
              const av = (doc.antivirus_status || "").toLowerCase();
              const unverified = AV_UNVERIFIED.has(av);
              const allIds = [doc.id, ...group.duplicates.map((d) => d.id)];
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
                        {dupOpen && onDelete ? (
                          <button
                            type="button"
                            className="linkish danger-link"
                            disabled={busy}
                            onClick={() =>
                              onDelete(
                                group.duplicates.map((d) => d.id),
                                `повторы файла «${shortName(doc)}» (${group.duplicates.length})`,
                              )
                            }
                            title="Оставить один экземпляр, повторные загрузки удалить"
                          >
                            Удалить повторы ({group.duplicates.length})
                          </button>
                        ) : null}
                      </div>
                    ) : null}
                    {summary ? (
                      <p className="hint" style={{ margin: "0.25rem 0 0" }}>
                        <strong>Краткое описание.</strong> {summary}
                      </p>
                    ) : null}
                    {row.warning ? (
                      <p className="hint warning-inline" style={{ margin: "0.25rem 0 0" }}>
                        {row.warning}
                      </p>
                    ) : null}
                  </td>
                  <td>
                    {row.canReviewText ? (
                      <button
                        type="button"
                        className="linkish"
                        disabled={busy}
                        title="Показать текст для проверки (без скачивания)"
                        aria-label={`Проверить текст: ${shortName(doc)}`}
                        onClick={() => openTextReview()}
                      >
                        Проверить текст
                      </button>
                    ) : (
                      row.state
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
                                ? "Антивирус не завершил проверку: открывайте осторожно"
                                : "Открыть PDF в новой вкладке без скачивания"
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
                        {hasFullText && (!row.canReviewText || textOpen) ? (
                          // При проверке кнопка в «Состоянии» — рядом «Текст» не дублируем.
                          <button
                            type="button"
                            className="linkish"
                            disabled={busy}
                            aria-label={`Текст: ${shortName(doc)}`}
                            onClick={() => toggleText(doc.id)}
                          >
                            {textOpen ? "Скрыть" : "Текст"}
                          </button>
                        ) : null}
                        {onDelete ? (
                          <button
                            type="button"
                            className="linkish danger-link"
                            disabled={busy}
                            aria-label={`Удалить: ${shortName(doc)}`}
                            onClick={() =>
                              onDelete(
                                allIds,
                                allIds.length > 1
                                  ? `файл «${shortName(doc)}» и его повторы (${allIds.length - 1})`
                                  : `файл «${shortName(doc)}»`,
                              )
                            }
                          >
                            Удалить
                          </button>
                        ) : null}
                      </span>
                    ) : (
                      <span className="docs-actions">
                        <span className="hint">
                          {AV_BLOCKED.has(av) ? "Заблокирован антивирусом" : "Файл ещё недоступен"}
                        </span>
                        {onDelete ? (
                          <button
                            type="button"
                            className="linkish danger-link"
                            disabled={busy}
                            onClick={() => onDelete(allIds, `файл «${shortName(doc)}»`)}
                          >
                            Удалить
                          </button>
                        ) : null}
                      </span>
                    )}
                    {textOpen ? (
                      <div className="docs-text-panel" style={{ marginTop: "0.5rem" }}>
                        {row.canReviewText && reviewReason ? (
                          <p className="hint" style={{ margin: "0 0 0.35rem" }}>
                            Почему нужна проверка: {reviewReason}
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
                            Полный текст сохранён отдельно — откройте его в «Проверке текста файлов».
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
