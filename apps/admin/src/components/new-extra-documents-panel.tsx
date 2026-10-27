"use client";

import { useCallback, useEffect, useState } from "react";

type ExtraDoc = {
  id: string;
  doc_type?: string | null;
  storage_path?: string;
  created_at?: string;
  upload_source?: string;
  ingest_status?: string | null;
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

async function staffFetch<T>(
  apiBase: string,
  path: string,
  token: string,
): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
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

  return (
    <div className="new-extra-documents">
      <h3 className="case-subhead">Новые документы</h3>
      <p className="hint">
        Входящие доп. материалы с любого этапа. Не сбрасывают оплату и согласования. Договор ≠
        подписан; квитанция ≠ оплата подтверждена. Входящие файлы не публикуются по общей ссылке
        Диска.
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
                disabled={busy}
                onClick={() => onOpenSigned(d.id)}
              >
                {(d.storage_path || "").split("/").pop() || d.id.slice(0, 8)}
              </button>
              <span className="hint">
                {" "}
                · {d.doc_type || "extra"} · {SOURCE_RU[d.upload_source || ""] || d.upload_source || "—"}{" "}
                · {d.created_at ? new Date(d.created_at).toLocaleString("ru-RU") : "—"}
                {d.ingest_status ? ` · ${d.ingest_status}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
      {unbound.length > 0 ? (
        <>
          <h3 className="case-subhead">Почта: требует привязки</h3>
          <p className="hint">
            Письма без кода SFRFR-DOC. Не добавлены в дело автоматически — привяжите вручную.
          </p>
          <ul className="plain-list">
            {unbound.slice(0, 15).map((u) => (
              <li key={u.id}>
                {u.subject || "(без темы)"} · {u.sender || "—"} · вложений:{" "}
                {(u.attachment_names || []).length}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      <button type="button" className="linkish" disabled={busy || loading} onClick={() => void reload()}>
        Обновить список
      </button>
    </div>
  );
}
