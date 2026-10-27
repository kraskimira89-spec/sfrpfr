"use client";

import { useCallback, useEffect, useState } from "react";

type ReviewStatus = "received" | "checked" | "needs_clarification";

type ExtraDoc = {
  id: string;
  doc_type?: string | null;
  storage_path?: string;
  created_at?: string;
  upload_source?: string;
  ingest_status?: string | null;
  review_status?: ReviewStatus | string;
  review_status_label?: string;
  analysis_update_needed?: boolean;
  review_note?: string | null;
};

type UnboundItem = {
  id: string;
  subject?: string;
  sender?: string;
  attachment_names?: string[];
  created_at?: string;
  status?: string;
};

const SOURCE_RU: Record<string, string> = {
  cabinet: "кабинет",
  email: "почта",
  chat: "чат",
  max: "MAX",
  staff: "сотрудник",
};

const STATUS_ACTIONS: { status: ReviewStatus; label: string }[] = [
  { status: "received", label: "Получен" },
  { status: "checked", label: "Проверен" },
  { status: "needs_clarification", label: "Нужно уточнение" },
];

async function staffFetch<T>(
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
      ...(init?.headers || {}),
    },
  });
  if (!response.ok) {
    throw new Error(((await response.text()) || `HTTP ${response.status}`).slice(0, 200));
  }
  return response.json() as Promise<T>;
}

export function NewExtraDocumentsPanel({
  caseId,
  token,
  apiBase,
  busy,
  onOpenSigned,
  onNotice,
}: {
  caseId: string;
  token: string;
  apiBase: string;
  busy?: boolean;
  onOpenSigned: (documentId: string) => void;
  onNotice: (msg: string) => void;
}) {
  const [docs, setDocs] = useState<ExtraDoc[]>([]);
  const [unbound, setUnbound] = useState<UnboundItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState(false);
  const [bindCaseByItem, setBindCaseByItem] = useState<Record<string, string>>({});

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [extra, queue] = await Promise.all([
        staffFetch<{ documents?: ExtraDoc[] }>(
          apiBase,
          `/api/portal/admin/cases/${caseId}/extra-documents`,
          token,
        ),
        staffFetch<{ items?: UnboundItem[] }>(
          apiBase,
          `/api/portal/admin/mail-inbound/unbound`,
          token,
        ).catch(() => ({ items: [] as UnboundItem[] })),
      ]);
      setDocs(extra.documents || []);
      setUnbound(queue.items || []);
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "Не удалось загрузить новые документы.");
    } finally {
      setLoading(false);
    }
  }, [apiBase, caseId, onNotice, token]);

  useEffect(() => {
    const t = window.setTimeout(() => void reload(), 0);
    return () => window.clearTimeout(t);
  }, [reload]);

  const setReview = async (
    documentId: string,
    status: ReviewStatus,
    opts?: { analysisUpdate?: boolean; note?: string },
  ) => {
    setActing(true);
    try {
      await staffFetch(apiBase, `/api/portal/admin/cases/${caseId}/extra-documents/${documentId}/review`, token, {
        method: "PATCH",
        body: JSON.stringify({
          status,
          analysis_update_needed: Boolean(opts?.analysisUpdate),
          note: opts?.note || null,
        }),
      });
      onNotice(
        opts?.analysisUpdate
          ? "Нужно обновить разбор — задача сотруднику. Оплата и согласования не сброшены."
          : `Статус: ${STATUS_ACTIONS.find((s) => s.status === status)?.label || status}`,
      );
      await reload();
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "Не удалось обновить статус.");
    } finally {
      setActing(false);
    }
  };

  const bindUnbound = async (itemId: string) => {
    const target = (bindCaseByItem[itemId] || caseId).trim();
    if (!target) {
      onNotice("Укажите id дела для привязки.");
      return;
    }
    setActing(true);
    try {
      const out = await staffFetch<{ detail?: string }>(
        apiBase,
        `/api/portal/admin/mail-inbound/unbound/${itemId}/bind`,
        token,
        {
          method: "POST",
          body: JSON.stringify({ case_id: target }),
        },
      );
      onNotice(out.detail || "Письмо привязано к делу. Добавьте вложения вручную.");
      await reload();
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "Не удалось привязать письмо.");
    } finally {
      setActing(false);
    }
  };

  const locked = Boolean(busy || acting || loading);

  return (
    <div className="new-extra-documents">
      <h3 className="case-subhead">Новые документы</h3>
      <p className="hint">
        Доп. материалы на любой ступени. Статусы: Получен / Проверен / Нужно уточнение. Не сбрасывают
        оплату и согласования. Договор ≠ подписан; квитанция ≠ оплата. Входящие файлы не публикуются
        по общей ссылке Диска.
      </p>
      {loading ? <p className="hint">Загрузка…</p> : null}
      {docs.length === 0 && !loading ? (
        <p className="hint">Пока нет документов категории «дополнительно».</p>
      ) : (
        <ul className="plain-list">
          {docs.map((d) => (
            <li key={d.id}>
              <button
                type="button"
                className="linkish"
                disabled={locked}
                onClick={() => onOpenSigned(d.id)}
              >
                {(d.storage_path || "").split("/").pop() || d.id.slice(0, 8)}
              </button>
              <span className="hint">
                {" "}
                · {d.doc_type || "extra"} · {SOURCE_RU[d.upload_source || ""] || d.upload_source || "—"}{" "}
                · {d.created_at ? new Date(d.created_at).toLocaleString("ru-RU") : "—"}
                {" · "}
                <strong>{d.review_status_label || d.review_status || "Получен"}</strong>
                {d.analysis_update_needed ? " · обновить разбор" : ""}
              </span>
              <div className="inline-form" style={{ marginTop: 4 }}>
                {STATUS_ACTIONS.map((a) => (
                  <button
                    key={a.status}
                    type="button"
                    className="linkish"
                    disabled={locked || d.review_status === a.status}
                    onClick={() => void setReview(d.id, a.status)}
                  >
                    {a.label}
                  </button>
                ))}
                <button
                  type="button"
                  className="linkish"
                  disabled={locked}
                  onClick={() =>
                    void setReview(d.id, "needs_clarification", {
                      analysisUpdate: true,
                      note: "Сотрудник подтвердил: нужно обновить разбор",
                    })
                  }
                >
                  Нужно обновить разбор
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {unbound.length > 0 ? (
        <>
          <h3 className="case-subhead">Почта: требует привязки</h3>
          <p className="hint">
            Письма без кода SFRFR-DOC. Не добавлены автоматически — укажите дело и привяжите вручную.
            Вложения из очереди не скачиваются сами: после привязки добавьте файлы в дело.
          </p>
          <ul className="plain-list">
            {unbound.slice(0, 15).map((u) => (
              <li key={u.id}>
                {u.subject || "(без темы)"} · {u.sender || "—"} · вложений:{" "}
                {(u.attachment_names || []).length}
                <div className="inline-form" style={{ marginTop: 4 }}>
                  <input
                    value={bindCaseByItem[u.id] ?? caseId}
                    onChange={(e) =>
                      setBindCaseByItem((prev) => ({ ...prev, [u.id]: e.target.value }))
                    }
                    placeholder="id дела"
                    disabled={locked}
                    aria-label="id дела для привязки"
                  />
                  <button
                    type="button"
                    disabled={locked}
                    onClick={() => void bindUnbound(u.id)}
                  >
                    Привязать к делу
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      ) : null}
      <button type="button" className="linkish" disabled={locked} onClick={() => void reload()}>
        Обновить список
      </button>
    </div>
  );
}
