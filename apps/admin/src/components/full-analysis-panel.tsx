"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  FULL_ANALYSIS_DRAFT_TIMEOUT_MS,
  draftTimeoutMessage,
  isAbortLikeError,
  reconcileDraftAfterClientFailure,
} from "@/lib/full-analysis-ui";

type Version = {
  id: string;
  n: number;
  status: string;
  markdown?: string;
  sent_via?: string | null;
  delivery_error?: string | null;
  client_revision_document_id?: string | null;
  remarks?: string | null;
};

type StatusStrip = {
  file: string;
  reviewed: string;
  sent: string;
  approved: string;
  delivery_error?: string | null;
  version_n?: number;
  status?: string;
  sent_via?: string | null;
};

type StatePayload = {
  current?: Version | null;
  current_id?: string | null;
  versions?: Version[];
  status_strip?: StatusStrip;
};

export type GenerateFullAnalysisDraftOpts = {
  signal?: AbortSignal;
};

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
      ...(init?.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const raw = (await response.text()) || `HTTP ${response.status}`;
    throw new Error(raw.slice(0, 240));
  }
  if (response.status === 204) return {} as T;
  const ct = response.headers.get("content-type") || "";
  if (ct.includes("application/json")) return response.json() as Promise<T>;
  return {} as T;
}

const STATUS_RU: Record<string, string> = {
  draft: "черновик",
  staff_reviewed: "проверен",
  sent: "отправлен на согласование",
  approved: "согласован клиентом",
  remarks: "есть замечания",
  superseded: "заменён",
};

export function FullAnalysisPanel({
  caseId,
  token,
  apiBase,
  clientEmail,
  busy,
  onNotice,
  onRefresh,
  onApplyChat,
  onGenerateDraft,
}: {
  caseId: string;
  token: string;
  apiBase: string;
  clientEmail?: string | null;
  busy: boolean;
  onNotice: (msg: string) => void;
  onRefresh: () => void;
  onApplyChat: (text: string) => void;
  onGenerateDraft?: (opts?: GenerateFullAnalysisDraftOpts) => Promise<string | null>;
}) {
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [state, setState] = useState<StatePayload | null>(null);
  const [draft, setDraft] = useState("");
  const draftDirtyRef = useRef(false);
  const generatingRef = useRef(false);
  const [emailOverride, setEmailOverride] = useState<string | null>(null);
  const emailTo = emailOverride ?? (clientEmail || "");
  const [emailPreview, setEmailPreview] = useState<{
    subject?: string;
    body?: string;
    attachment?: string;
  } | null>(null);

  const markDraftDirty = useCallback((value: boolean) => {
    draftDirtyRef.current = value;
  }, []);

  const reload = useCallback(
    async (opts?: { preserveDirtyDraft?: boolean }) => {
      setLoading(true);
      try {
        const out = await staffFetch<StatePayload & { ok?: boolean }>(
          apiBase,
          `/api/portal/admin/cases/${caseId}/full-analysis/state`,
          token,
        );
        setState(out);
        const md = out.current?.markdown || "";
        const keepLocal = Boolean(opts?.preserveDirtyDraft && draftDirtyRef.current);
        if (md && !keepLocal) {
          setDraft(md);
          markDraftDirty(false);
        }
        return out;
      } catch (error) {
        onNotice(error instanceof Error ? error.message : "Не удалось загрузить разбор.");
        return null;
      } finally {
        setLoading(false);
      }
    },
    [apiBase, caseId, markDraftDirty, onNotice, token],
  );

  useEffect(() => {
    const t = window.setTimeout(() => void reload(), 0);
    return () => window.clearTimeout(t);
  }, [reload]);

  const current = state?.current ?? null;
  const strip = state?.status_strip;
  const versionId = current?.id;

  async function generateAi() {
    if (!onGenerateDraft || generatingRef.current) return;
    generatingRef.current = true;
    setGenerating(true);
    const beforeId = versionId ?? null;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), FULL_ANALYSIS_DRAFT_TIMEOUT_MS);
    try {
      const text = await onGenerateDraft({ signal: controller.signal });
      if (text) {
        setDraft(text);
        markDraftDirty(false);
        onNotice("Черновик ИИ готов — проверьте и отметьте «Проверено».");
        await reload({ preserveDirtyDraft: false });
        onRefresh();
        return;
      }
      // Пустой ответ — сверяем, не создал ли сервер версию.
      const after = await reload({ preserveDirtyDraft: true });
      const recovered = reconcileDraftAfterClientFailure({
        beforeId,
        after: after?.current ?? null,
      });
      if (recovered.recovered) {
        setDraft(recovered.markdown);
        markDraftDirty(false);
        onNotice(recovered.notice);
        onRefresh();
      } else {
        onNotice("ИИ не вернул текст. Можно повторить подготовку разбора.");
      }
    } catch (error) {
      // Сервер мог ещё писать версию после обрыва ответа на клиенте — коротко подождём.
      let recovered = reconcileDraftAfterClientFailure({
        beforeId,
        after: (await reload({ preserveDirtyDraft: true }))?.current ?? null,
      });
      if (!recovered.recovered && (isAbortLikeError(error) || controller.signal.aborted)) {
        for (let i = 0; i < 5 && !recovered.recovered; i += 1) {
          await new Promise((r) => window.setTimeout(r, 2000));
          recovered = reconcileDraftAfterClientFailure({
            beforeId,
            after: (await reload({ preserveDirtyDraft: true }))?.current ?? null,
          });
        }
      }
      if (recovered.recovered) {
        setDraft(recovered.markdown);
        markDraftDirty(false);
        onNotice(recovered.notice);
        onRefresh();
        return;
      }
      if (isAbortLikeError(error) || controller.signal.aborted) {
        onNotice(draftTimeoutMessage(FULL_ANALYSIS_DRAFT_TIMEOUT_MS));
      } else {
        onNotice(error instanceof Error ? error.message : "Не удалось сгенерировать разбор.");
      }
    } finally {
      window.clearTimeout(timer);
      generatingRef.current = false;
      setGenerating(false);
    }
  }

  async function saveEdits() {
    if (!versionId) {
      onNotice("Сначала подготовьте разбор с ИИ.");
      return;
    }
    try {
      await staffFetch(
        apiBase,
        `/api/portal/admin/cases/${caseId}/full-analysis/versions/${versionId}`,
        token,
        { method: "PUT", body: JSON.stringify({ markdown: draft }) },
      );
      onNotice("Текст версии сохранён.");
      markDraftDirty(false);
      await reload({ preserveDirtyDraft: false });
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "Не удалось сохранить.");
    }
  }

  async function markReviewed() {
    if (!versionId) return;
    try {
      await saveEdits();
      await staffFetch(
        apiBase,
        `/api/portal/admin/cases/${caseId}/full-analysis/versions/${versionId}/review`,
        token,
        { method: "POST", body: "{}" },
      );
      onNotice("Версия отмечена как проверенная сотрудником.");
      await reload();
      onRefresh();
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "Не удалось отметить проверку.");
    }
  }

  async function downloadDocx() {
    if (!versionId) return;
    try {
      await saveEdits();
      const response = await fetch(
        `${apiBase}/api/portal/admin/cases/${caseId}/full-analysis/versions/${versionId}/docx`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (!response.ok) throw new Error((await response.text()).slice(0, 200));
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `razbor-v${current?.n || 1}.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "Не удалось скачать Word.");
    }
  }

  async function previewOrSendEmail(confirm: boolean) {
    if (!versionId) return;
    try {
      await saveEdits();
      const out = await staffFetch<{
        ok?: boolean;
        preview?: boolean;
        subject?: string;
        body?: string;
        attachment?: string;
        error?: string;
        detail?: string;
        honest?: boolean;
      }>(
        apiBase,
        `/api/portal/admin/cases/${caseId}/full-analysis/versions/${versionId}/send-email`,
        token,
        {
          method: "POST",
          body: JSON.stringify({
            to: emailTo,
            confirm,
            subject: emailPreview?.subject,
            body: emailPreview?.body,
          }),
        },
      );
      if (out.preview) {
        setEmailPreview({
          subject: out.subject,
          body: out.body,
          attachment: out.attachment,
        });
        onNotice("Превью письма готово — проверьте адрес и нажмите «Отправить на почту».");
        return;
      }
      if (out.ok) {
        setEmailPreview(null);
        onNotice("Письмо с Word отправлено. Этап ещё не закрыт — нужно согласование клиента.");
        await reload();
        onRefresh();
        return;
      }
      onNotice(
        out.error
          ? `Отправка не удалась: ${out.error}${out.detail ? ` (${out.detail})` : ""}. Статус «Отправлено» не выставлен.`
          : "Отправка не удалась.",
      );
      await reload();
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "Ошибка почты.");
    }
  }

  async function previewOrSendYadisk(confirm: boolean) {
    if (!versionId) return;
    try {
      await saveEdits();
      const out = await staffFetch<{
        ok?: boolean;
        preview?: boolean;
        public_url?: string;
        chat_hint?: string;
        error?: string;
        hint?: string;
        honest?: boolean;
        filename?: string;
      }>(
        apiBase,
        `/api/portal/admin/cases/${caseId}/full-analysis/versions/${versionId}/send-yadisk`,
        token,
        { method: "POST", body: JSON.stringify({ confirm }) },
      );
      if (out.preview) {
        onNotice(
          `Превью Диска: файл ${out.filename || "docx"} (~байт известен). Подтвердите отправку ссылки.`,
        );
        return;
      }
      if (out.ok && out.public_url) {
        onNotice("Ссылка на Яндекс Диск готова. Этап не закрыт без согласования.");
        if (out.chat_hint) onApplyChat(out.chat_hint);
        await reload();
        onRefresh();
        return;
      }
      onNotice(
        [
          out.error ? `Диск: ${out.error}` : "Не удалось выдать ссылку",
          out.hint,
          "Статус «Отправлено» не выставлен.",
        ]
          .filter(Boolean)
          .join(" — "),
      );
      await reload();
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "Ошибка Яндекс Диска.");
    }
  }

  async function decide(decision: "approved" | "remarks") {
    if (!versionId) return;
    const remarks =
      decision === "remarks"
        ? window.prompt("Кратко зафиксируйте замечания клиента:") || ""
        : "";
    if (decision === "remarks" && !remarks.trim()) {
      onNotice("Нужен текст замечаний.");
      return;
    }
    if (
      !window.confirm(
        decision === "approved"
          ? "Зафиксировать согласование этой версии клиентом? Этап 5 будет закрыт."
          : "Зафиксировать замечания? Потребуется новая версия разбора.",
      )
    )
      return;
    try {
      await staffFetch(
        apiBase,
        `/api/portal/admin/cases/${caseId}/full-analysis/versions/${versionId}/decision`,
        token,
        { method: "POST", body: JSON.stringify({ decision, remarks }) },
      );
      onNotice(
        decision === "approved"
          ? "Клиент согласовал разбор — этап 5 можно считать завершённым."
          : "Замечания зафиксированы — подготовьте новую версию с ИИ.",
      );
      await reload();
      onRefresh();
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "Не удалось записать решение.");
    }
  }

  async function uploadClientRevision(file: File) {
    if (!versionId) return;
    const form = new FormData();
    form.append("file", file);
    form.append("note", "Версия клиента");
    try {
      await staffFetch(
        apiBase,
        `/api/portal/admin/cases/${caseId}/full-analysis/versions/${versionId}/client-revision`,
        token,
        { method: "POST", body: form },
      );
      onNotice("Версия клиента сохранена — учтите правки в следующей редакции.");
      await reload();
      onRefresh();
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "Не удалось сохранить файл клиента.");
    }
  }

  return (
    <div className="full-analysis-panel">
      <p className="hint">
        <strong>Выдача подробного разбора</strong>
        <br />
        ИИ готовит текст → сотрудник проверяет и правит → Word → отправка клиенту (почта или ссылка
        на Яндекс Диск) → клиент согласует или присылает замечания. Генерация и «Текст в чат»
        этап не закрывают.
      </p>

      <ul className="plain-list" style={{ marginBottom: "0.75rem" }}>
        <li>
          Файл: <strong>{strip?.file ?? "—"}</strong>
          {strip?.version_n ? ` (v${strip.version_n})` : ""}
        </li>
        <li>
          Проверен сотрудником: <strong>{strip?.reviewed ?? "—"}</strong>
        </li>
        <li>
          Отправлен на согласование: <strong>{strip?.sent ?? "—"}</strong>
          {strip?.sent_via ? ` · ${strip.sent_via}` : ""}
        </li>
        <li>
          Согласован клиентом: <strong>{strip?.approved ?? "—"}</strong>
        </li>
        {strip?.delivery_error ? (
          <li>
            Ошибка доставки: <strong>{strip.delivery_error}</strong> (не считается «отправлено»)
          </li>
        ) : null}
        {current?.status ? (
          <li>
            Статус версии: <strong>{STATUS_RU[current.status] || current.status}</strong>
          </li>
        ) : null}
      </ul>

      <div className="row-actions">
        {onGenerateDraft ? (
          <button
            type="button"
            disabled={busy || generating || loading}
            onClick={() => void generateAi()}
          >
            {generating ? "ИИ готовит…" : "Подготовить подробный разбор с ИИ"}
          </button>
        ) : null}
        <button
          type="button"
          className="secondary"
          disabled={busy || !versionId}
          onClick={() => void saveEdits()}
        >
          Сохранить правки
        </button>
        <button
          type="button"
          disabled={busy || !versionId}
          onClick={() => void markReviewed()}
          title="Без этой отметки отправка на согласование недоступна"
        >
          Проверено сотрудником
        </button>
        <button
          type="button"
          className="secondary"
          disabled={busy || !versionId}
          onClick={() => void downloadDocx()}
        >
          Скачать Word
        </button>
        <button
          type="button"
          className="linkish"
          disabled={busy || !draft.trim()}
          onClick={() => onApplyChat(draft)}
          title="Только подставляет текст справа; в MAX — после «Отправить»"
        >
          Текст в чат…
        </button>
      </div>

      {draft ? (
        <textarea
          className="draft"
          style={{ width: "100%", minHeight: "14rem", marginTop: "0.5rem" }}
          value={draft}
          disabled={busy}
          onChange={(e) => {
            setDraft(e.target.value);
            markDraftDirty(true);
          }}
          aria-label="Черновик подробного разбора"
        />
      ) : (
        <p className="hint">
          {loading
            ? "Загрузка…"
            : "Нажмите «Подготовить подробный разбор с ИИ». Непроверенный текст клиенту не уходит."}
        </p>
      )}

      <h3 className="case-subhead">Отправка на согласование</h3>
      <p className="hint">
        Сначала превью, затем явное подтверждение. Ошибка ≠ статус «Отправлено». Согласование
        разбора не равно согласию на обращения (этап 6).
      </p>
      <div className="row-actions" style={{ alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
        <input
          type="email"
          placeholder="Почта клиента"
          value={emailTo}
          onChange={(e) => setEmailOverride(e.target.value)}
          disabled={busy}
          style={{ minWidth: "14rem" }}
        />
        <button
          type="button"
          className="secondary"
          disabled={busy || !versionId}
          onClick={() => void previewOrSendEmail(false)}
        >
          Превью письма
        </button>
        <button
          type="button"
          disabled={busy || !versionId || !emailPreview}
          onClick={() => {
            if (
              !window.confirm(
                `Отправить Word на ${emailTo}? Версия v${current?.n ?? "—"}.`,
              )
            )
              return;
            void previewOrSendEmail(true);
          }}
        >
          Отправить на почту
        </button>
        <button
          type="button"
          className="secondary"
          disabled={busy || !versionId}
          onClick={() => void previewOrSendYadisk(false)}
        >
          Превью ссылки Диска
        </button>
        <button
          type="button"
          disabled={busy || !versionId}
          onClick={() => {
            if (!window.confirm("Загрузить Word на Диск и выдать публичную ссылку на файл?"))
              return;
            void previewOrSendYadisk(true);
          }}
        >
          Отправить ссылку на Яндекс Диск
        </button>
      </div>
      {emailPreview ? (
        <pre className="draft" style={{ maxHeight: "10rem", overflow: "auto" }}>
          Кому: {emailTo}
          {"\n"}Тема: {emailPreview.subject}
          {"\n"}Вложение: {emailPreview.attachment}
          {"\n\n"}
          {emailPreview.body}
        </pre>
      ) : null}

      <h3 className="case-subhead">Ответ клиента</h3>
      <div className="row-actions">
        <button
          type="button"
          disabled={busy || !versionId}
          onClick={() => void decide("approved")}
        >
          Согласовать разбор
        </button>
        <button
          type="button"
          className="secondary"
          disabled={busy || !versionId}
          onClick={() => void decide("remarks")}
        >
          Есть замечания
        </button>
        <label className="secondary" style={{ cursor: busy ? "wait" : "pointer" }}>
          Версия клиента…
          <input
            type="file"
            accept=".docx,.doc,.pdf,.md,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            hidden
            disabled={busy || !versionId}
            onChange={(e) => {
              const f = e.target.files?.[0];
              e.target.value = "";
              if (f) void uploadClientRevision(f);
            }}
          />
        </label>
      </div>
      {current?.remarks ? <p className="hint">Замечания: {current.remarks}</p> : null}
      {current?.client_revision_document_id ? (
        <p className="hint">
          Сохранена версия клиента (doc {current.client_revision_document_id.slice(0, 8)}…).
        </p>
      ) : null}

      {(state?.versions || []).length > 1 ? (
        <>
          <h3 className="case-subhead">Версии</h3>
          <ul className="plain-list">
            {(state?.versions || [])
              .slice()
              .reverse()
              .map((v) => (
                <li key={v.id}>
                  v{v.n} · {STATUS_RU[v.status] || v.status}
                  {v.id === versionId ? " · текущая" : ""}
                </li>
              ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}
