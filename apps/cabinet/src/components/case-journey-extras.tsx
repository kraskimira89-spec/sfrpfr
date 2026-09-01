"use client";

import { useEffect, useState } from "react";
import type { CabinetDocument } from "@/components/documents-table";

type LaborEstimate = {
  status?: string;
  pages_count?: number;
  preliminary_total_rub?: number;
  rate_per_spread_rub?: number;
  message?: string;
};

type Props = {
  caseId: string;
  token: string;
  apiBase: string;
  documents: CabinetDocument[];
  busy?: boolean;
  pendingGroupIds: string[];
  onClearPendingGroup: () => void;
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
  pendingGroupIds,
  onClearPendingGroup,
  onRefresh,
  onPay,
  onNotice,
}: Props) {
  const [estimate, setEstimate] = useState<LaborEstimate | null>(null);
  const [estimateBusy, setEstimateBusy] = useState(false);
  const [progressRows, setProgressRows] = useState<Record<string, string>>({});

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
          const payload = await apiJson<{ progress_message?: string; status_label?: string }>(
            apiBase,
            `/api/portal/cases/${caseId}/documents/${doc.id}/progress`,
            token,
          );
          if (!cancelled) {
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
  }, [apiBase, caseId, documents, token]);

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

  async function groupPendingPhotos() {
    if (pendingGroupIds.length < 2) return;
    try {
      await apiJson(apiBase, `/api/portal/cases/${caseId}/document-groups`, token, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: "Документ из фотографий",
          doc_type: "labor",
          document_ids: pendingGroupIds,
        }),
      });
      onNotice("Страницы объединены в один логический документ.");
      onClearPendingGroup();
      await onRefresh();
    } catch {
      onNotice("Не удалось объединить фотографии.");
    }
  }

  const showLabor = documents.some((d) =>
    ["labor", "workbook"].includes(String(d.doc_type || "").toLowerCase()),
  );

  return (
    <>
      {pendingGroupIds.length >= 2 ? (
        <section className="panel">
          <h2>Объединить фотографии</h2>
          <p className="hint">
            Вы загрузили {pendingGroupIds.length} файла. Можно собрать их в один документ с
            порядком страниц.
          </p>
          <p className="home-actions">
            <button type="button" disabled={busy} onClick={() => void groupPendingPhotos()}>
              Объединить в один документ
            </button>
            <button type="button" className="secondary" disabled={busy} onClick={onClearPendingGroup}>
              Оставить отдельными файлами
            </button>
          </p>
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
