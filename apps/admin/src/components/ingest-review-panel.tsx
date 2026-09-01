"use client";

import { useCallback, useEffect, useState } from "react";

type ReviewDocument = {
  id: string;
  filename?: string | null;
  ingest_status?: string | null;
  progress_message?: string | null;
  antivirus_status?: string | null;
  ingest_review_required?: boolean;
  content_preview?: string | null;
};

type ManifestPage = {
  page?: number;
  source?: string;
  char_count?: number;
  engine?: string | null;
  error?: string | null;
};

type Props = {
  caseId: string;
  token: string;
  busy?: boolean;
  canEdit?: boolean;
  onNotice: (text: string) => void;
  onRefresh: () => void;
};

async function requestJson<T>(
  apiBase: string,
  path: string,
  token: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export function IngestReviewPanel({
  caseId,
  token,
  busy,
  canEdit = false,
  onNotice,
  onRefresh,
}: Props) {
  const [documents, setDocuments] = useState<ReviewDocument[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [initialTexts, setInitialTexts] = useState<Record<string, string>>({});
  const [pages, setPages] = useState<Record<string, ManifestPage[]>>({});
  const [originalUrls, setOriginalUrls] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);

  const loadReviewQueue = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const payload = await requestJson<{ documents?: ReviewDocument[] }>(
        apiBase,
        `/api/portal/admin/cases/${caseId}/ingest-review`,
        token,
      );
      setDocuments(payload.documents || []);
    } catch {
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  }, [caseId, token]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadReviewQueue(), 0);
    return () => window.clearTimeout(timer);
  }, [loadReviewQueue]);

  async function showArtifacts(document: ReviewDocument) {
    if (!canEdit) return;
    if (expandedId === document.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(document.id);
    if (texts[document.id] !== undefined) return;
    try {
      const payload = await requestJson<{
        extracted_text?: string;
        manifest?: { pages?: ManifestPage[] };
      }>(
        apiBase,
        `/api/portal/admin/cases/${caseId}/documents/${document.id}/ingest-artifacts`,
        token,
      );
      setTexts((previous) => ({ ...previous, [document.id]: payload.extracted_text || "" }));
      setInitialTexts((previous) => ({ ...previous, [document.id]: payload.extracted_text || "" }));
      setPages((previous) => ({ ...previous, [document.id]: payload.manifest?.pages || [] }));
      try {
        const original = await requestJson<{ url?: string }>(
          apiBase,
          `/api/portal/cases/${caseId}/documents/${document.id}/signed-url`,
          token,
          { method: "POST" },
        );
        if (original.url) {
          setOriginalUrls((previous) => ({ ...previous, [document.id]: original.url || "" }));
        }
      } catch {
        /* Оригинал может быть закрыт до завершения проверки безопасности. */
      }
    } catch {
      onNotice("Артефакты ingest пока недоступны.");
    }
  }

  async function openOriginal(document: ReviewDocument) {
    if (!canEdit) return;
    try {
      const payload = await requestJson<{ url?: string }>(
        apiBase,
        `/api/portal/cases/${caseId}/documents/${document.id}/signed-url`,
        token,
        { method: "POST" },
      );
      if (!payload.url) throw new Error("signed URL missing");
      setOriginalUrls((previous) => ({ ...previous, [document.id]: payload.url || "" }));
      window.open(payload.url, "_blank", "noopener,noreferrer");
    } catch {
      onNotice("Оригинал пока недоступен: сначала завершите проверку безопасности.");
    }
  }

  async function action(
    document: ReviewDocument,
    path: string,
    body?: Record<string, unknown>,
  ) {
    setActionBusy(true);
    try {
      await requestJson(
        apiBase,
        `/api/portal/admin/cases/${caseId}/documents/${document.id}/${path}`,
        token,
        body ? { method: "POST", body: JSON.stringify(body) } : { method: "POST" },
      );
      onNotice("Статус документа обновлён.");
      await loadReviewQueue();
      onRefresh();
    } catch {
      onNotice("Не удалось обновить статус документа.");
    } finally {
      setActionBusy(false);
    }
  }

  if (loading || documents.length === 0) return null;

  return (
    <section className="panel" aria-labelledby="ingest-review-title">
      <h2 id="ingest-review-title">Проверка файлов ingest</h2>
      <p className="hint">
        {canEdit
          ? "Проверьте безопасность, сверяйте текст с оригиналом и принимайте результат."
          : "Здесь видны документы на проверке. При проблеме запросите у клиента пересъёмку."}
      </p>
      <ul className="plain-list">
        {documents.map((document) => {
          const documentText = texts[document.id] || "";
          const documentPages = pages[document.id] || [];
          return (
            <li key={document.id} className="ingest-review-item">
              <div className="ingest-review-head">
                <strong>{document.filename || "Документ"}</strong>
                <span className="hint">
                  {document.antivirus_status || "security"} ·{" "}
                  {document.ingest_status || "неизвестно"}
                </span>
              </div>
              <p className="hint">{document.progress_message || "Нужна проверка."}</p>
              <div className="row-actions">
                {canEdit ? (
                  <button
                    type="button"
                    disabled={busy || actionBusy}
                    onClick={() => void openOriginal(document)}
                  >
                    Открыть оригинал
                  </button>
                ) : null}
                {canEdit ? (
                  <button
                    type="button"
                    disabled={busy || actionBusy}
                    onClick={() => void showArtifacts(document)}
                  >
                    {expandedId === document.id ? "Скрыть текст" : "Открыть текст"}
                  </button>
                ) : null}
                {canEdit && document.antivirus_status !== "clean" ? (
                  <button
                    type="button"
                    disabled={busy || actionBusy}
                    onClick={() => void action(document, "security-approve")}
                  >
                    Подтвердить безопасность
                  </button>
                ) : null}
                {canEdit ? (
                  <button
                    type="button"
                    disabled={busy || actionBusy || !documentText.trim()}
                    onClick={() =>
                      void action(document, "ingest-accept", {
                        extracted_text: documentText,
                        text_edited: initialTexts[document.id] !== documentText,
                      })
                    }
                  >
                    Принять текст
                  </button>
                ) : null}
                {canEdit && document.antivirus_status === "clean" ? (
                  <button
                    type="button"
                    disabled={busy || actionBusy}
                    onClick={() => void action(document, "ingest-rerun")}
                  >
                    Перезапустить OCR
                  </button>
                ) : null}
                <button
                  type="button"
                  className="secondary"
                  disabled={busy || actionBusy}
                  onClick={() =>
                    void action(document, "ingest-reject", {
                      reason:
                        window.prompt(
                          "Что нужно исправить?",
                          "Нужна более чёткая копия документа.",
                        ) || "",
                    })
                  }
                >
                  Запросить пересъёмку
                </button>
              </div>
              {canEdit && expandedId === document.id ? (
                <div className="ingest-review-split">
                  <div className="ingest-review-original">
                    <strong>Оригинал</strong>
                    {originalUrls[document.id] ? (
                      <iframe
                        title={`Оригинал: ${document.filename || "документ"}`}
                        src={originalUrls[document.id]}
                      />
                    ) : (
                      <p className="hint">Оригинал станет доступен после проверки безопасности.</p>
                    )}
                  </div>
                  <div className="ingest-review-editor">
                    <label>
                      Текст для проверки
                      <textarea
                        rows={8}
                        value={documentText}
                        onChange={(event) =>
                          setTexts((previous) => ({
                            ...previous,
                            [document.id]: event.target.value,
                          }))
                        }
                      />
                    </label>
                    {documentPages.length > 0 ? (
                      <ul className="plain-list ingest-review-pages">
                        {documentPages.map((page) => (
                          <li key={`${page.page}-${page.source}`}>
                            Стр. {page.page}: {page.source || "—"} · {page.char_count || 0} симв.
                            {page.error ? ` · ${page.error}` : ""}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
