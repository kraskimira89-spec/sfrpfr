"use client";

import { useEffect, useMemo, useState, type DragEvent } from "react";
import type { CabinetDocument } from "@/components/documents-table";

export type PendingGroupPage = {
  id: string;
  filename: string;
  file?: File;
};

type LaborEstimate = {
  status?: string;
  pages_count?: number;
  preliminary_total_rub?: number;
  rate_per_spread_rub?: number;
  message?: string;
};

type DocumentGroup = {
  id: string;
  title?: string | null;
  page_count?: number;
  pages: CabinetDocument[];
};

type Props = {
  caseId: string;
  token: string;
  apiBase: string;
  documents: CabinetDocument[];
  busy?: boolean;
  pendingGroupPages: PendingGroupPage[];
  pendingGroupDocType?: string;
  onClearPendingGroup: (documentIds: string[]) => void;
  onRefresh: () => void;
  onPay: (orderId: string) => void;
  onNotice: (text: string) => void;
};

async function apiJson<T>(
  apiBase: string,
  path: string,
  token: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export function CaseJourneyExtras({
  caseId,
  token,
  apiBase,
  documents,
  busy,
  pendingGroupPages,
  pendingGroupDocType,
  onClearPendingGroup,
  onRefresh,
  onPay,
  onNotice,
}: Props) {
  const [estimate, setEstimate] = useState<LaborEstimate | null>(null);
  const [estimateBusy, setEstimateBusy] = useState(false);
  const [progressRows, setProgressRows] = useState<Record<string, string>>({});
  const [orderedPages, setOrderedPages] = useState<PendingGroupPage[]>(pendingGroupPages);
  const [selectedPageIds, setSelectedPageIds] = useState<string[]>(
    pendingGroupPages.map((page) => page.id),
  );
  const [draggedPageId, setDraggedPageId] = useState<string | null>(null);
  const [groups, setGroups] = useState<DocumentGroup[]>([]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setOrderedPages(pendingGroupPages);
      setSelectedPageIds((previous) => {
        const available = new Set(pendingGroupPages.map((page) => page.id));
        const retained = previous.filter((id) => available.has(id));
        return retained.length > 0 ? retained : pendingGroupPages.map((page) => page.id);
      });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [pendingGroupPages]);

  useEffect(() => {
    let cancelled = false;
    const loadGroups = async () => {
      try {
        const payload = await apiJson<{ groups?: DocumentGroup[] }>(
          apiBase,
          `/api/portal/cases/${caseId}/document-groups`,
          token,
        );
        if (!cancelled) setGroups(payload.groups || []);
      } catch {
        /* Группы недоступны, основной список документов продолжает работать. */
      }
    };
    void loadGroups();
    return () => {
      cancelled = true;
    };
  }, [apiBase, caseId, documents, token]);

  const pendingPlacement = documents.filter((doc) => {
    const suggestion = doc.placement_suggestion as
      | { needs_confirmation?: boolean; confirmed_requirement_code?: string }
      | undefined;
    return suggestion?.needs_confirmation && !suggestion?.confirmed_requirement_code;
  });

  useEffect(() => {
    const pending = documents.filter(
      (doc) =>
        doc.ingest_status &&
        !["under_review", "accepted", "needs_reupload", "blocked_security"].includes(
          String(doc.ingest_status),
        ) &&
        Number(doc.progress_percent ?? 100) < 100,
    );
    if (pending.length === 0) return undefined;
    let cancelled = false;
    const tick = async () => {
      for (const doc of pending) {
        try {
          const payload = await apiJson<{
            progress_message?: string;
            status_label?: string;
            progress_percent?: number;
            ingest_status?: string;
          }>(
            apiBase,
            `/api/portal/cases/${caseId}/documents/${doc.id}/progress`,
            token,
          );
          if (!cancelled) {
            if (Number(payload.progress_percent ?? 0) >= 100) {
              setProgressRows((prev) => {
                const next = { ...prev };
                delete next[doc.id];
                return next;
              });
              window.setTimeout(() => void onRefresh(), 0);
              continue;
            }
            setProgressRows((prev) => ({
              ...prev,
              [doc.id]: payload.progress_message || payload.status_label || "Обрабатываем…",
            }));
          }
        } catch {
          /* ignore */
        }
      }
    };
    void tick();
    const timer = window.setInterval(() => void tick(), 4000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [apiBase, caseId, documents, onRefresh, token]);

  async function loadLaborEstimate() {
    setEstimateBusy(true);
    try {
      const payload = await apiJson<LaborEstimate>(
        apiBase,
        `/api/portal/cases/${caseId}/labor-transcription/estimate`,
        token,
        { method: "POST" },
      );
      setEstimate(payload);
      onNotice(payload.message || "Оценка переноса готова.");
    } catch {
      onNotice("Не удалось оценить перенос трудовой.");
    } finally {
      setEstimateBusy(false);
    }
  }

  async function confirmLaborOrder() {
    setEstimateBusy(true);
    try {
      const payload = await apiJson<{ order?: { id?: string }; estimate?: LaborEstimate }>(
        apiBase,
        `/api/portal/cases/${caseId}/labor-transcription/confirm`,
        token,
        { method: "POST" },
      );
      const orderId = payload.order?.id;
      onNotice(
        payload.estimate?.message ||
          "Заказ на перенос создан. Оплатите, чтобы мы начали работу.",
      );
      if (orderId) onPay(orderId);
      await onRefresh();
    } catch {
      onNotice("Не удалось подтвердить заказ на перенос.");
    } finally {
      setEstimateBusy(false);
    }
  }

  async function confirmPlacement(documentId: string, requirementCode: string) {
    try {
      await apiJson(
        apiBase,
        `/api/portal/cases/${caseId}/documents/${documentId}/confirm-placement`,
        token,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ requirement_code: requirementCode }),
        },
      );
      onNotice("Размещение подтверждено. Специалист проверит документ.");
      await onRefresh();
    } catch {
      onNotice("Не удалось подтвердить размещение.");
    }
  }

  function reorderPages(sourceId: string, targetId: string) {
    if (sourceId === targetId) return;
    setOrderedPages((previous) => {
      const sourceIndex = previous.findIndex((page) => page.id === sourceId);
      const targetIndex = previous.findIndex((page) => page.id === targetId);
      if (sourceIndex < 0 || targetIndex < 0) return previous;
      const next = [...previous];
      const [moved] = next.splice(sourceIndex, 1);
      next.splice(targetIndex, 0, moved);
      return next;
    });
  }

  function handlePageDrop(event: DragEvent<HTMLLIElement>, targetId: string) {
    event.preventDefault();
    if (draggedPageId) reorderPages(draggedPageId, targetId);
    setDraggedPageId(null);
  }

  function movePage(pageId: string, offset: -1 | 1) {
    setOrderedPages((previous) => {
      const index = previous.findIndex((page) => page.id === pageId);
      const nextIndex = index + offset;
      if (index < 0 || nextIndex < 0 || nextIndex >= previous.length) return previous;
      const next = [...previous];
      [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
      return next;
    });
  }

  function togglePage(pageId: string) {
    setSelectedPageIds((previous) =>
      previous.includes(pageId)
        ? previous.filter((id) => id !== pageId)
        : [...previous, pageId],
    );
  }

  async function groupPendingPhotos() {
    const selected = orderedPages.filter((page) => selectedPageIds.includes(page.id));
    if (selected.length < 2) {
      onNotice("Выберите минимум две страницы для объединения.");
      return;
    }
    try {
      await apiJson(apiBase, `/api/portal/cases/${caseId}/document-groups`, token, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: "Документ из фотографий",
          doc_type: pendingGroupDocType || "photo_document",
          document_ids: selected.map((page) => page.id),
        }),
      });
      onNotice(
        `Страницы объединены в один логический документ (${selected.length} стр.).`,
      );
      onClearPendingGroup(selected.map((page) => page.id));
      await onRefresh();
    } catch {
      onNotice("Не удалось объединить фотографии.");
    }
  }

  async function downloadGroup(group: DocumentGroup) {
    const documentIds = group.pages.map((page) => page.id);
    if (documentIds.length === 0) return;
    try {
      const response = await fetch(
        `${apiBase}/api/portal/cases/${caseId}/documents/bulk-download`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ document_ids: documentIds }),
        },
      );
      if (!response.ok) throw new Error("download failed");
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        const payload = (await response.json()) as { url?: string };
        if (payload.url) window.open(payload.url, "_blank", "noopener,noreferrer");
      } else {
        const url = URL.createObjectURL(await response.blob());
        const link = document.createElement("a");
        link.href = url;
        link.download = `${group.title || "document-group"}.pdf`;
        link.click();
        URL.revokeObjectURL(url);
      }
      onNotice("Единый PDF документа подготовлен.");
    } catch {
      onNotice("Не удалось скачать собранный документ.");
    }
  }

  const showLabor = documents.some((d) =>
    ["labor", "labor_book", "workbook"].includes(String(d.doc_type || "").toLowerCase()),
  );

  return (
    <>
      {orderedPages.length >= 2 ? (
        <section className="panel">
          <h2>Соберите страницы в документ</h2>
          <p className="hint">
            Перетащите карточки в правильный порядок. Отмеченные страницы будут объединены в
            один логический документ; остальные останутся отдельными файлами.
          </p>
          <ol className="photo-group-list">
            {orderedPages.map((page, index) => {
              const checked = selectedPageIds.includes(page.id);
              return (
                <li
                  key={page.id}
                  className={`photo-group-card${draggedPageId === page.id ? " is-dragged" : ""}`}
                  draggable={!busy}
                  onDragStart={() => setDraggedPageId(page.id)}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={(event) => handlePageDrop(event, page.id)}
                  onDragEnd={() => setDraggedPageId(null)}
                >
                  <span className="photo-group-handle" aria-hidden="true">
                    ⋮⋮
                  </span>
                  <input
                    type="checkbox"
                    aria-label={`Включить страницу ${index + 1}`}
                    checked={checked}
                    disabled={busy}
                    onChange={() => togglePage(page.id)}
                  />
                  <PageThumbnail page={page} />
                  <span className="photo-group-name">
                    <strong>Страница {index + 1}</strong>
                    <span>{page.filename}</span>
                  </span>
                  <span className="photo-group-reorder">
                    <button
                      type="button"
                      className="linkish"
                      aria-label={`Переместить страницу ${index + 1} выше`}
                      disabled={busy || index === 0}
                      onClick={() => movePage(page.id, -1)}
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      className="linkish"
                      aria-label={`Переместить страницу ${index + 1} ниже`}
                      disabled={busy || index === orderedPages.length - 1}
                      onClick={() => movePage(page.id, 1)}
                    >
                      ↓
                    </button>
                  </span>
                </li>
              );
            })}
          </ol>
          <p className="home-actions">
            <button type="button" disabled={busy || selectedPageIds.length < 2} onClick={() => void groupPendingPhotos()}>
              Объединить выбранные ({selectedPageIds.length})
            </button>
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => onClearPendingGroup(orderedPages.map((page) => page.id))}
            >
              Оставить отдельными файлами
            </button>
          </p>
          <p className="hint">Можно перетаскивать карточки мышью или менять порядок стрелками.</p>
        </section>
      ) : null}

      {groups.length > 0 ? (
        <section className="panel">
          <h2>Собранные документы</h2>
          {groups.map((group) => (
            <div key={group.id} className="photo-group-saved">
              <div>
                <strong>{group.title || "Документ из фотографий"}</strong>
                <span className="hint">
                  {" "}
                  · {group.page_count || group.pages.length} стр.
                </span>
              </div>
              <ol className="plain-list photo-group-saved-pages">
                {group.pages.map((page, index) => (
                  <li key={page.id}>
                    Страница {index + 1}: {page.filename || "файл"}
                  </li>
                ))}
              </ol>
              <button
                type="button"
                className="secondary"
                disabled={busy}
                onClick={() => void downloadGroup(group)}
              >
                Скачать единым PDF
              </button>
            </div>
          ))}
        </section>
      ) : null}

      {pendingPlacement.length > 0 ? (
        <section className="panel">
          <h2>Подтвердите тип документа</h2>
          <p className="hint">Предварительный результат — требуется ваше подтверждение.</p>
          <ul className="plain-list">
            {pendingPlacement.map((doc) => {
              const suggestion = doc.placement_suggestion as {
                label?: string;
                requirement_code?: string;
                client_message?: string;
              };
              const code = suggestion?.requirement_code || "extra";
              return (
                <li key={doc.id}>
                  <strong>{doc.filename || doc.inner_title || "Файл"}</strong>
                  <p className="hint">{suggestion?.client_message}</p>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void confirmPlacement(doc.id, code)}
                  >
                    Поместить: {suggestion?.label || code}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      {Object.keys(progressRows).length > 0 ? (
        <section className="panel" aria-live="polite">
          <h2>Проверка и распознавание</h2>
          <ul className="plain-list">
            {Object.entries(progressRows).map(([id, message]) => {
              const doc = documents.find((row) => row.id === id);
              return (
                <li key={id}>
                  <strong>{doc?.filename || "Файл"}</strong> — {message}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      {showLabor ? (
        <section className="panel">
          <h2>Перенос трудовой в Word</h2>
          <p className="hint">
            Отдельная услуга: 100 ₽ за разворот. Перенос помогает сверке, но не подтверждает стаж —
            решение принимает СФР.
          </p>
          {estimate?.status === "estimate_ready" ? (
            <p>
              Оценка: <strong>{estimate.pages_count}</strong> разворотов ·{" "}
              <strong>{estimate.preliminary_total_rub?.toLocaleString("ru-RU")} ₽</strong>
            </p>
          ) : null}
          <p className="home-actions">
            <button
              type="button"
              disabled={busy || estimateBusy}
              onClick={() => void loadLaborEstimate()}
            >
              Узнать стоимость переноса
            </button>
            {estimate?.status === "estimate_ready" ? (
              <button
                type="button"
                disabled={busy || estimateBusy}
                onClick={() => void confirmLaborOrder()}
              >
                Подтвердить и оплатить
              </button>
            ) : null}
          </p>
        </section>
      ) : null}
    </>
  );
}

function PageThumbnail({ page }: { page: PendingGroupPage }) {
  const previewUrl = useMemo(() => {
    if (!page.file || !page.file.type.startsWith("image/")) return null;
    return URL.createObjectURL(page.file);
  }, [page.file]);
  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  if (previewUrl) {
    return <img className="photo-group-thumb" src={previewUrl} alt="" />;
  }
  return <span className="photo-group-thumb photo-group-thumb--empty">Фото</span>;
}
