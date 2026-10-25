"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { StepNo } from "@/components/step-number";
import {
  antivirusLabel,
  canBulkAccept,
  groupReviewDocs,
  ingestStatusLabel,
  pageSourceLabel,
  reviewSummary,
  type ReviewDoc,
  type ReviewGroup,
} from "@/lib/ingest-review-view";

type ManifestPage = {
  page?: number;
  source?: string;
  char_count?: number;
  engine?: string | null;
  error?: string | null;
};

type ArtifactsPayload = {
  extracted_text?: string;
  manifest?: { pages?: ManifestPage[] };
  fallback?: boolean;
  truncated?: boolean;
};

type Props = {
  caseId: string;
  token: string;
  busy?: boolean;
  canEdit?: boolean;
  onNotice: (text: string) => void;
  onRefresh: () => void;
};

type PrimaryKind =
  | "open_original"
  | "open_text"
  | "security_approve"
  | "accept_text"
  | "cloud_later"
  | "request_reshoot"
  | "none";

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
  if (!response.ok) {
    const raw = (await response.text()) || `HTTP ${response.status}`;
    let detail = raw;
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      if (typeof parsed.detail === "string" && parsed.detail.trim()) {
        detail = parsed.detail;
      }
    } catch {
      /* сырой текст */
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
const AV_PENDING = new Set(["pending", "error"]);

function needsReview(doc: ReviewDoc): boolean {
  return Boolean(doc.ingest_review_required) || (doc.ingest_status || "") === "manual_review";
}

function primaryFor(doc: ReviewDoc, hasText: boolean): { kind: PrimaryKind; label: string } {
  const status = (doc.ingest_status || "").toLowerCase();
  const av = (doc.antivirus_status || "").toLowerCase();
  if (status === "needs_reupload" && doc.has_local_file) {
    return { kind: "cloud_later", label: "На сервере, облако позже" };
  }
  if (status === "needs_reupload") {
    return { kind: "request_reshoot", label: "Запросить пересъёмку" };
  }
  if (AV_PENDING.has(av) || status === "security_check") {
    return { kind: "security_approve", label: "Подтвердить безопасность" };
  }
  if (!hasText) return { kind: "open_text", label: "Открыть текст для проверки" };
  if (needsReview(doc)) return { kind: "accept_text", label: "Принять текст" };
  return { kind: "open_original", label: "Открыть оригинал" };
}

function filesWord(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "файл";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "файла";
  return "файлов";
}

export function IngestReviewPanel({
  caseId,
  token,
  busy,
  canEdit = false,
  onNotice,
  onRefresh,
}: Props) {
  const [documents, setDocuments] = useState<ReviewDoc[]>([]);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [initialTexts, setInitialTexts] = useState<Record<string, string>>({});
  const [textNotes, setTextNotes] = useState<Record<string, string>>({});
  const [pages, setPages] = useState<Record<string, ManifestPage[]>>({});
  const [originalUrls, setOriginalUrls] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);

  const groups = useMemo(() => groupReviewDocs(documents), [documents]);
  const summary = useMemo(() => reviewSummary(groups), [groups]);

  const loadReviewQueue = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const payload = await requestJson<{ documents?: ReviewDoc[] }>(
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

  /** Полный текст файла; если артефактов нет — сохранённый текст из карточки. */
  async function fetchText(group: ReviewGroup): Promise<{ text: string; note: string }> {
    try {
      const payload = await requestJson<ArtifactsPayload>(
        apiBase,
        `/api/portal/admin/cases/${caseId}/documents/${group.primary.id}/ingest-artifacts`,
        token,
      );
      setPages((previous) => ({ ...previous, [group.key]: payload.manifest?.pages || [] }));
      const note = payload.fallback
        ? payload.truncated
          ? "Показан сохранённый текст (первые 2000 символов)."
          : "Показан сохранённый текст."
        : "";
      return { text: payload.extracted_text || "", note };
    } catch {
      const saved = (group.primary.content_preview || "").trim();
      return {
        text: saved,
        note: saved ? "Показан сохранённый текст из карточки." : "",
      };
    }
  }

  async function showText(group: ReviewGroup) {
    if (!canEdit) return;
    if (expandedKey === group.key) {
      setExpandedKey(null);
      return;
    }
    setExpandedKey(group.key);
    if (texts[group.key] !== undefined) return;
    const { text, note } = await fetchText(group);
    if (!text) onNotice("Текст файла не сохранён — откройте оригинал или распознайте заново.");
    setTexts((previous) => ({ ...previous, [group.key]: text }));
    setInitialTexts((previous) => ({ ...previous, [group.key]: text }));
    setTextNotes((previous) => ({ ...previous, [group.key]: note }));
    try {
      const original = await requestJson<{ url?: string }>(
        apiBase,
        `/api/portal/cases/${caseId}/documents/${group.primary.id}/signed-url`,
        token,
        { method: "POST" },
      );
      if (original.url) {
        setOriginalUrls((previous) => ({ ...previous, [group.key]: original.url || "" }));
      }
    } catch {
      /* Оригинал может быть закрыт до завершения проверки безопасности. */
    }
  }

  async function openOriginal(group: ReviewGroup) {
    if (!canEdit) return;
    try {
      const payload = await requestJson<{ url?: string }>(
        apiBase,
        `/api/portal/cases/${caseId}/documents/${group.primary.id}/signed-url`,
        token,
        { method: "POST" },
      );
      if (!payload.url) throw new Error("Ссылка на оригинал не получена");
      setOriginalUrls((previous) => ({ ...previous, [group.key]: payload.url || "" }));
      window.open(payload.url, "_blank", "noopener,noreferrer");
    } catch (error) {
      onNotice(
        error instanceof Error
          ? error.message
          : "Оригинал недоступен (права или проверка безопасности).",
      );
    }
  }

  /** Действие для всех копий файла; возвращает число успешных. */
  async function forCopies(
    docs: ReviewDoc[],
    path: string,
    body?: Record<string, unknown>,
  ): Promise<number> {
    let ok = 0;
    for (const doc of docs) {
      try {
        await requestJson(
          apiBase,
          `/api/portal/admin/cases/${caseId}/documents/${doc.id}/${path}`,
          token,
          body ? { method: "POST", body: JSON.stringify(body) } : { method: "POST" },
        );
        ok += 1;
      } catch {
        /* считаем ниже */
      }
    }
    return ok;
  }

  async function act(group: ReviewGroup, path: string, body?: Record<string, unknown>) {
    const targets =
      path === "security-approve"
        ? group.copies.filter((d) => AV_PENDING.has((d.antivirus_status || "").toLowerCase()))
        : group.copies.filter(needsReview);
    const list = targets.length > 0 ? targets : [group.primary];
    setActionBusy(true);
    try {
      const ok = await forCopies(list, path, body);
      onNotice(
        ok === list.length
          ? list.length > 1
            ? `Готово для всех копий: ${ok}.`
            : "Статус документа обновлён."
          : `Обновлено ${ok} из ${list.length}. Остальные — повторите позже.`,
      );
      await loadReviewQueue();
      onRefresh();
    } finally {
      setActionBusy(false);
    }
  }

  async function deleteGroup(group: ReviewGroup) {
    const name = group.primary.filename || "документ";
    const copies = group.copies.length;
    if (
      !window.confirm(
        copies > 1
          ? `Удалить файл «${name}» и его повторы (${copies - 1})? Восстановить будет нельзя.`
          : `Удалить файл «${name}»? Восстановить будет нельзя.`,
      )
    ) {
      return;
    }
    setActionBusy(true);
    let ok = 0;
    let lastError = "";
    try {
      for (const doc of group.copies) {
        try {
          await requestJson(
            apiBase,
            `/api/portal/admin/cases/${caseId}/documents/${doc.id}`,
            token,
            { method: "DELETE" },
          );
          ok += 1;
        } catch (error) {
          lastError = error instanceof Error ? error.message : "ошибка удаления";
        }
      }
      onNotice(
        ok === copies ? `Удалено файлов: ${ok}.` : `Удалено ${ok} из ${copies}. ${lastError}`.trim(),
      );
      if (expandedKey === group.key) setExpandedKey(null);
      await loadReviewQueue();
      onRefresh();
    } finally {
      setActionBusy(false);
    }
  }

  async function bulkAccept() {
    const eligible = groups.filter(canBulkAccept);
    if (eligible.length === 0) return;
    if (
      !window.confirm(
        `Принять текст у ${eligible.length} ${filesWord(eligible.length)} PDF/Word? ` +
          "Это файлы с текстовым слоем — текст в них точный. Сканы и фото проверьте вручную.",
      )
    ) {
      return;
    }
    setActionBusy(true);
    let done = 0;
    try {
      for (const group of eligible) {
        const { text } = await fetchText(group);
        if (!text.trim()) continue;
        const ok = await forCopies(group.copies.filter(needsReview), "ingest-accept", {
          extracted_text: text,
          text_edited: false,
        });
        if (ok > 0) done += 1;
      }
      onNotice(`Текст принят у ${done} из ${eligible.length} ${filesWord(eligible.length)}.`);
      await loadReviewQueue();
      onRefresh();
    } finally {
      setActionBusy(false);
    }
  }

  async function runPrimary(group: ReviewGroup, kind: PrimaryKind) {
    const groupText = texts[group.key] || "";
    if (kind === "open_original") return openOriginal(group);
    if (kind === "open_text") return showText(group);
    if (kind === "security_approve") return act(group, "security-approve");
    if (kind === "accept_text") {
      return act(group, "ingest-accept", {
        extracted_text: groupText,
        text_edited: initialTexts[group.key] !== groupText,
      });
    }
    if (kind === "request_reshoot") {
      return act(group, "ingest-reject", {
        reason:
          window.prompt("Что нужно исправить?", "Нужна более чёткая копия документа.") || "",
      });
    }
  }

  if (loading || groups.length === 0) return null;

  return (
    <details className="panel ingest-review">
      <summary className="ingest-review-summary">
        <StepNo n={4} /> <strong>Проверка текста файлов</strong>
        <span className="hint">
          {" "}
          · ждут: {summary.files} {filesWord(summary.files)}
          {summary.copies > summary.files ? ` (с копиями — ${summary.copies})` : ""}
          {canEdit && summary.bulk > 0 ? ` · можно принять сразу: ${summary.bulk}` : ""}
        </span>
      </summary>
      <p className="hint">
        {canEdit
          ? "Сверьте текст с оригиналом и примите его — от этого зависит точность проверки и резюме. Повторные загрузки одного файла объединены: действие применяется ко всем копиям."
          : "Файлы ждут проверки специалистом. Пересъёмка — только если файла нет на сервере."}
      </p>
      {canEdit && summary.bulk > 0 ? (
        <div className="row-actions">
          <button
            type="button"
            disabled={busy || actionBusy}
            onClick={() => void bulkAccept()}
            title="Только PDF и Word с текстовым слоем; сканы и фото — вручную"
          >
            Принять текст у PDF/Word ({summary.bulk})
          </button>
        </div>
      ) : null}
      <ul className="plain-list">
        {groups.map((group) => {
          const doc = group.primary;
          const groupText = texts[group.key] || "";
          const groupPages = pages[group.key] || [];
          const primary = primaryFor(doc, Boolean(groupText.trim()));
          const showReshootSecondary =
            canEdit && primary.kind !== "request_reshoot" && primary.kind !== "cloud_later";
          return (
            <li key={group.key} className="ingest-review-item">
              <div className="ingest-review-head">
                <strong>{doc.filename || "Документ"}</strong>
                {group.copies.length > 1 ? (
                  <span className="hint"> · копий: {group.copies.length}</span>
                ) : null}
                <span className="hint">
                  {" "}
                  · {ingestStatusLabel(doc)} · {antivirusLabel(doc.antivirus_status)}
                </span>
              </div>
              <p className="hint">
                {primary.kind === "cloud_later"
                  ? "Файл на сервере; загрузка в облако позже. Клиента не просим снимать заново."
                  : doc.progress_message || "Нужна проверка."}
              </p>
              <div className="row-actions">
                {canEdit && primary.kind !== "none" && primary.kind !== "cloud_later" ? (
                  <button
                    type="button"
                    disabled={
                      busy || actionBusy || (primary.kind === "accept_text" && !groupText.trim())
                    }
                    onClick={() => void runPrimary(group, primary.kind)}
                  >
                    {primary.label}
                    {primary.kind === "accept_text" && group.copies.length > 1
                      ? ` (все копии: ${group.copies.length})`
                      : ""}
                  </button>
                ) : null}
                {primary.kind === "cloud_later" ? (
                  <span className="hint">{primary.label}</span>
                ) : null}
                {canEdit ? (
                  <details className="ingest-more">
                    <summary className="linkish">Ещё</summary>
                    <div className="row-actions">
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy || actionBusy}
                        onClick={() => void openOriginal(group)}
                      >
                        Открыть оригинал
                      </button>
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy || actionBusy}
                        onClick={() => void showText(group)}
                      >
                        {expandedKey === group.key ? "Скрыть текст" : "Открыть текст"}
                      </button>
                      {(doc.antivirus_status || "") !== "clean" ? (
                        <button
                          type="button"
                          className="secondary"
                          disabled={busy || actionBusy}
                          onClick={() => void act(group, "security-approve")}
                        >
                          Подтвердить безопасность
                        </button>
                      ) : null}
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy || actionBusy || !groupText.trim()}
                        onClick={() =>
                          void act(group, "ingest-accept", {
                            extracted_text: groupText,
                            text_edited: initialTexts[group.key] !== groupText,
                          })
                        }
                      >
                        Принять текст
                      </button>
                      {(doc.antivirus_status || "") === "clean" ? (
                        <button
                          type="button"
                          className="secondary"
                          disabled={busy || actionBusy}
                          onClick={() => void act(group, "ingest-rerun")}
                        >
                          Распознать заново
                        </button>
                      ) : null}
                      {showReshootSecondary ? (
                        <button
                          type="button"
                          className="secondary"
                          disabled={busy || actionBusy}
                          onClick={() => void runPrimary(group, "request_reshoot")}
                        >
                          Запросить пересъёмку
                        </button>
                      ) : null}
                      <button
                        type="button"
                        className="secondary danger-button"
                        disabled={busy || actionBusy}
                        onClick={() => void deleteGroup(group)}
                        title="Удалить файл и все его повторы (мусор, ошибочная загрузка)"
                      >
                        {group.copies.length > 1
                          ? `Удалить (все копии: ${group.copies.length})`
                          : "Удалить"}
                      </button>
                    </div>
                  </details>
                ) : (
                  <button
                    type="button"
                    className="secondary"
                    disabled={busy || actionBusy || primary.kind === "cloud_later"}
                    onClick={() => void runPrimary(group, "request_reshoot")}
                  >
                    {primary.kind === "cloud_later"
                      ? "На сервере, облако позже"
                      : "Запросить пересъёмку"}
                  </button>
                )}
              </div>
              {canEdit && expandedKey === group.key ? (
                <div className="ingest-review-split">
                  <div className="ingest-review-original">
                    <strong>Оригинал</strong>
                    {originalUrls[group.key] ? (
                      <iframe
                        title={`Оригинал: ${doc.filename || "документ"}`}
                        src={originalUrls[group.key]}
                      />
                    ) : (
                      <p className="hint">
                        Оригинал станет доступен после проверки безопасности.
                      </p>
                    )}
                  </div>
                  <div className="ingest-review-editor">
                    <label>
                      Текст для проверки
                      <textarea
                        rows={8}
                        value={groupText}
                        onChange={(event) =>
                          setTexts((previous) => ({
                            ...previous,
                            [group.key]: event.target.value,
                          }))
                        }
                      />
                    </label>
                    {textNotes[group.key] ? (
                      <p className="hint">{textNotes[group.key]}</p>
                    ) : null}
                    {groupPages.length > 0 ? (
                      <ul className="plain-list ingest-review-pages">
                        {groupPages.map((page) => (
                          <li key={`${page.page}-${page.source}`}>
                            Стр. {page.page}: {pageSourceLabel(page.source)} ·{" "}
                            {page.char_count || 0} симв.
                            {page.error ? ` · ошибка: ${page.error}` : ""}
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
    </details>
  );
}
