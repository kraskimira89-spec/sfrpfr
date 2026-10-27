"use client";

import { useMemo, useState } from "react";
import type { FollowUpControlPayload } from "@/components/follow-up-stage-panel";
import type { SubmissionReportView } from "@/components/submission-stage-panel";
import {
  incomingDocLabel,
  type IncomingResponseDoc,
} from "@/lib/incoming-response-docs";

export type ResponseReviewView = {
  id?: string;
  document_id?: string | null;
  submission_report_id?: string | null;
  doc_date?: string | null;
  doc_number?: string | null;
  received_at?: string | null;
  source?: string | null;
  completeness?: string | null;
  respondent?: string | null;
  respondent_label?: string | null;
  response_kind?: string | null;
  status?: string | null;
  deadline_quote?: string | null;
  deadline_quote_source?: string | null;
  deadline_quote_page?: string | null;
  ai_draft_md?: string | null;
  staff_draft_md?: string | null;
  reviewed_at?: string | null;
  sent_at?: string | null;
  sent_channel?: string | null;
  outcome?: string | null;
  outcome_at?: string | null;
  created_at?: string | null;
};

export type SfrResponseDoc = IncomingResponseDoc;

export type AmountsChronologyRow = {
  date?: string | null;
  effective_date?: string | null;
  document_date?: string | null;
  received_date?: string | null;
  filename?: string;
  page?: string | null;
  monthly_before_rub?: number | null;
  monthly_after_rub?: number | null;
  lump_sum_rub?: number | null;
  amount_kind?: string | null;
  payment_status?: string | null;
  basis_quote?: string | null;
  conflict_group?: string | null;
  note?: string;
};

export type IncomingUploadOpts = {
  doc_type: "sfr_decision" | "agency_response";
  respondent: string;
  submission_report_id?: string;
};

const RESPONDENT_OPTIONS: { value: string; label: string }[] = [
  { value: "sfr", label: "СФР" },
  { value: "employer", label: "Работодатель" },
  { value: "archive", label: "Архив" },
  { value: "court", label: "Суд" },
  { value: "mfc", label: "МФЦ" },
  { value: "other", label: "Иное" },
];

const STATUS_LABELS: Record<string, string> = {
  received: "получен",
  reviewing: "разбирается",
  reviewed: "проверен",
};

const OUTCOME_LABELS: Record<string, string> = {
  need_docs: "Нужны документы / пояснения",
  offer_escalation: "Предложить доп. обращения (ступень 12)",
  close: "Передать на завершение (ступень 13)",
  wait_client: "Клиент пока не решил",
};

type MatrixRow = {
  key: string;
  submissionId: string | null;
  submissionLabel: string;
  review: ResponseReviewView | null;
  file: SfrResponseDoc | null;
  fileLabel: string;
  organ: string;
  status: string;
};

type Props = {
  busy: boolean;
  token: string;
  apiBase: string;
  caseId: string;
  clientEmail?: string | null;
  reviews: ResponseReviewView[];
  submissionReports: SubmissionReportView[];
  sfrDocuments: SfrResponseDoc[];
  clientReportedWithoutDoc?: boolean;
  canEdit: boolean;
  onReload: () => Promise<void> | void;
  onUploadIncoming?: (file: File, opts: IncomingUploadOpts) => void | Promise<void>;
  /** @deprecated use onUploadIncoming */
  onUploadSfr?: (file: File) => void;
  onApplyChat: (text: string) => void;
  onFollowUpControl?: (payload: FollowUpControlPayload) => Promise<void> | void;
  onOpenDoc?: (docId: string) => void;
  onAmountsExtracted?: (amounts: {
    beforeRub: string;
    afterRub: string;
    lumpRub: string;
  }) => void;
};

async function apiJson<T>(
  url: string,
  token: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init?.headers || {}),
    },
  });
  const data = (await res.json().catch(() => ({}))) as T & { detail?: string };
  if (!res.ok) {
    throw new Error(
      typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`,
    );
  }
  return data;
}

function submissionLabel(r: SubmissionReportView | null | undefined): string {
  if (!r) return "(без привязки к подаче)";
  const bits = [
    (r.submitted_on || "").toString().slice(0, 10),
    r.method || "",
    (r.submitted_what || "").toString().slice(0, 40),
  ].filter(Boolean);
  return bits.join(" · ") || (r.id || "").slice(0, 8) || "подача";
}

function buildMatrix(
  reports: SubmissionReportView[],
  reviews: ResponseReviewView[],
  docs: SfrResponseDoc[],
): MatrixRow[] {
  const byDoc = new Map(docs.map((d) => [d.id, d]));
  const reviewDocIds = new Set(
    reviews.map((r) => r.document_id).filter(Boolean) as string[],
  );
  const rows: MatrixRow[] = [];

  for (const rev of reviews) {
    const sub = reports.find((r) => r.id === rev.submission_report_id) || null;
    const file = rev.document_id ? byDoc.get(rev.document_id) || null : null;
    rows.push({
      key: `rev:${rev.id}`,
      submissionId: rev.submission_report_id || null,
      submissionLabel: submissionLabel(sub),
      review: rev,
      file,
      fileLabel: file
        ? incomingDocLabel(file)
        : (rev.document_id || "").slice(0, 8) || "—",
      organ: rev.respondent_label || rev.respondent || "СФР",
      status: STATUS_LABELS[rev.status || ""] || rev.status || "—",
    });
  }

  for (const doc of docs) {
    if (reviewDocIds.has(doc.id)) continue;
    rows.push({
      key: `doc:${doc.id}`,
      submissionId: null,
      submissionLabel: "(файл без регистрации)",
      review: null,
      file: doc,
      fileLabel: incomingDocLabel(doc),
      organ: (doc.doc_type || "").includes("agency") ? "иное" : "СФР?",
      status: "нет разбора",
    });
  }

  if (reports.length > 0 && rows.every((r) => r.submissionId === null)) {
    // покажем подачи без ответа
  }
  for (const rep of reports) {
    const has = rows.some((r) => r.submissionId === rep.id);
    if (!has) {
      rows.push({
        key: `sub:${rep.id}`,
        submissionId: rep.id || null,
        submissionLabel: submissionLabel(rep),
        review: null,
        file: null,
        fileLabel: "—",
        organ: "—",
        status: "нет файла",
      });
    }
  }

  return rows;
}

export function ResponseReviewPanel({
  busy,
  token,
  apiBase,
  caseId,
  clientEmail,
  reviews,
  submissionReports,
  sfrDocuments,
  clientReportedWithoutDoc,
  canEdit,
  onReload,
  onUploadIncoming,
  onUploadSfr,
  onApplyChat,
  onFollowUpControl,
  onOpenDoc,
  onAmountsExtracted,
}: Props) {
  const matrix = useMemo(
    () => buildMatrix(submissionReports, reviews, sfrDocuments),
    [submissionReports, reviews, sfrDocuments],
  );

  const [selectedId, setSelectedId] = useState(reviews[0]?.id || "");
  const [draft, setDraft] = useState(() =>
    String(reviews[0]?.staff_draft_md || reviews[0]?.ai_draft_md || ""),
  );
  const [loadedForId, setLoadedForId] = useState<string | null>(
    reviews[0]?.id || null,
  );
  const [deadlineQuote, setDeadlineQuote] = useState("");
  const [deadlineSource, setDeadlineSource] = useState("");
  const [deadlinePage, setDeadlinePage] = useState("");
  const [controlLocal, setControlLocal] = useState("");
  const [emailTo, setEmailTo] = useState(clientEmail || "");
  const [msg, setMsg] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [chronology, setChronology] = useState<AmountsChronologyRow[]>([]);
  const [amountsQuote, setAmountsQuote] = useState<string | null>(null);

  const [bindDocId, setBindDocId] = useState(sfrDocuments[0]?.id || "");
  const [bindSubmissionId, setBindSubmissionId] = useState(
    submissionReports[0]?.id || "",
  );
  const [respondent, setRespondent] = useState("sfr");
  const [uploadDocType, setUploadDocType] = useState<"sfr_decision" | "agency_response">(
    "sfr_decision",
  );
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>(() =>
    sfrDocuments.map((d) => d.id),
  );
  const [amountsWarnings, setAmountsWarnings] = useState<string[]>([]);

  const selected = useMemo(() => {
    const id = selectedId || reviews[0]?.id;
    return reviews.find((r) => r.id === id) || reviews[0] || null;
  }, [reviews, selectedId]);

  if (selected?.id && selected.id !== loadedForId) {
    setLoadedForId(selected.id);
    setDraft(String(selected.staff_draft_md || selected.ai_draft_md || ""));
    setDeadlineQuote(String(selected.deadline_quote || ""));
    setDeadlineSource(String(selected.deadline_quote_source || ""));
    setDeadlinePage(String(selected.deadline_quote_page || ""));
  }

  const base = `${apiBase}/api/portal/admin/cases/${caseId}/response-review`;
  const locked = busy || working || !canEdit;

  async function registerFile(docId: string, submissionId?: string) {
    setWorking(true);
    setMsg(null);
    try {
      const out = await apiJson<{ review?: ResponseReviewView; replayed?: boolean }>(
        `${base}/register`,
        token,
        {
          method: "POST",
          body: JSON.stringify({
            document_id: docId,
            submission_report_id: submissionId || undefined,
            source: "staff",
            completeness: "unknown",
            respondent,
            response_kind: "decision",
            idempotency_key: `register:${docId}:${submissionId || "none"}`,
          }),
        },
      );
      if (out.review?.id) setSelectedId(out.review.id);
      setMsg(out.replayed ? "Уже зарегистрирован." : "Ответ зарегистрирован.");
      await onReload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Ошибка регистрации");
    } finally {
      setWorking(false);
    }
  }

  async function aiDraft() {
    if (!selected?.id) return;
    setWorking(true);
    try {
      const out = await apiJson<{ text?: string; source?: string; reason?: string }>(
        `${base}/${selected.id}/ai-draft`,
        token,
        { method: "POST", body: "{}" },
      );
      setDraft(String(out.text || ""));
      setMsg(
        out.source === "template"
          ? `Шаблон (${out.reason || "без ИИ"}) — проверьте вручную.`
          : "ИИ подготовил проект. Проверьте источники.",
      );
      await onReload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Ошибка ИИ");
    } finally {
      setWorking(false);
    }
  }

  async function saveDraft() {
    if (!selected?.id) return;
    setWorking(true);
    try {
      await apiJson(`${base}/${selected.id}`, token, {
        method: "PUT",
        body: JSON.stringify({ staff_draft_md: draft }),
      });
      setMsg("Правки сохранены.");
      await onReload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Ошибка сохранения");
    } finally {
      setWorking(false);
    }
  }

  async function markReviewed() {
    if (!selected?.id) return;
    setWorking(true);
    try {
      await apiJson(`${base}/${selected.id}/review`, token, {
        method: "POST",
        body: JSON.stringify({ staff_draft_md: draft }),
      });
      setMsg("Разбор отмечен как проверенный.");
      await onReload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setWorking(false);
    }
  }

  async function downloadDocx() {
    if (!selected?.id) return;
    const res = await fetch(`${base}/${selected.id}/docx`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      setMsg(`Word: HTTP ${res.status}`);
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `otvet-organ.docx`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function sendEmail(confirm: boolean) {
    if (!selected?.id) return;
    setWorking(true);
    try {
      const out = await apiJson<{ ok?: boolean; preview?: boolean; error?: string }>(
        `${base}/${selected.id}/send-email`,
        token,
        { method: "POST", body: JSON.stringify({ to: emailTo, confirm }) },
      );
      if (out.preview && !confirm) {
        setMsg(`Превью письма → ${emailTo}. Подтвердите «Отправить почтой».`);
      } else if (out.ok) {
        setMsg("Письмо отправлено.");
        await onReload();
      } else {
        setMsg(out.error || "Отправка не удалась");
      }
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Ошибка почты");
    } finally {
      setWorking(false);
    }
  }

  async function sendYadisk(confirm: boolean) {
    if (!selected?.id) return;
    setWorking(true);
    try {
      const out = await apiJson<{
        ok?: boolean;
        preview?: boolean;
        error?: string;
        public_url?: string;
        chat_hint?: string;
      }>(`${base}/${selected.id}/send-yadisk`, token, {
        method: "POST",
        body: JSON.stringify({ confirm }),
      });
      if (out.preview && !confirm) {
        setMsg("Превью Диска готово. Подтвердите отправку.");
      } else if (out.ok) {
        setMsg(out.public_url ? `Ссылка: ${out.public_url}` : "Загружено на Диск.");
        if (out.chat_hint) onApplyChat(out.chat_hint);
        await onReload();
      } else {
        setMsg(out.error || "Диск: ошибка");
      }
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Ошибка Диска");
    } finally {
      setWorking(false);
    }
  }

  async function setOutcome(outcome: string) {
    if (!selected?.id) return;
    setWorking(true);
    try {
      const out = await apiJson<{ note?: string | null }>(
        `${base}/${selected.id}/outcome`,
        token,
        { method: "POST", body: JSON.stringify({ outcome }) },
      );
      setMsg(
        out.note ||
          `${OUTCOME_LABELS[outcome] || outcome}. Счёт 8 000 ₽ не создан.`,
      );
      await onReload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Ошибка исхода");
    } finally {
      setWorking(false);
    }
  }

  async function applyDeadlineControl() {
    if (!selected?.id || !controlLocal) return;
    setWorking(true);
    try {
      await apiJson(`${base}/${selected.id}/set-deadline-control`, token, {
        method: "POST",
        body: JSON.stringify({ control_at: new Date(controlLocal).toISOString() }),
      });
      setMsg("Контроль назначен через ступень 10.");
      await onReload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Ошибка контроля");
    } finally {
      setWorking(false);
    }
  }

  async function extractAmounts(force = false) {
    const ids = selectedDocIds.length ? selectedDocIds : sfrDocuments.map((d) => d.id);
    if (ids.length === 0) {
      setMsg("Выберите хотя бы один файл ответа.");
      return;
    }
    setWorking(true);
    try {
      const out = await apiJson<{
        ok?: boolean;
        needs_confirm?: boolean;
        detail?: string;
        monthly_before_rub?: number | null;
        monthly_after_rub?: number | null;
        lump_sum_rub?: number | null;
        chronology?: AmountsChronologyRow[];
        source_quote?: string | null;
        source?: string;
        reason?: string | null;
        partial?: boolean;
        warnings?: string[];
        files?: { id?: string; filename?: string; has_text?: boolean }[];
      }>(`${base}/extract-amounts`, token, {
        method: "POST",
        body: JSON.stringify({ document_ids: ids, force }),
      });
      if (out.needs_confirm) {
        const ok = window.confirm(
          out.detail ||
            "Есть проверенные суммы. Повторное извлечение затрёт черновик. Продолжить?",
        );
        if (ok) {
          await extractAmounts(true);
        }
        return;
      }
      setChronology(Array.isArray(out.chronology) ? out.chronology : []);
      setAmountsQuote(out.source_quote || null);
      setAmountsWarnings(Array.isArray(out.warnings) ? out.warnings : []);
      const noText = (out.files || []).filter((f) => !f.has_text);
      const fmt = (n: number | null | undefined) =>
        n == null || !Number.isFinite(n) ? "" : String(Math.round(n * 100) / 100);
      onAmountsExtracted?.({
        beforeRub: fmt(out.monthly_before_rub),
        afterRub: fmt(out.monthly_after_rub),
        lumpRub: fmt(out.lump_sum_rub),
      });
      const parts: string[] = [];
      if (out.partial || noText.length) {
        parts.push(
          `Частично: нет OCR у ${noText.map((f) => f.filename || f.id).join(", ") || "части файлов"}`,
        );
      }
      if (out.source === "ai") {
        parts.push("Черновик сумм из ответов — проверьте и сохраните.");
      } else {
        parts.push(`Без уверенных сумм (${out.reason || "нет текста"}).`);
      }
      setMsg(parts.join(" "));
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Ошибка извлечения сумм");
    } finally {
      setWorking(false);
    }
  }

  function fmtAmt(n: number | null | undefined): string {
    return n == null || !Number.isFinite(n) ? "Не указано" : String(n);
  }

  function handleUpload(files: FileList | File[]) {
    const list = Array.from(files);
    for (const f of list) {
      if (onUploadIncoming) {
        void onUploadIncoming(f, {
          doc_type: uploadDocType,
          respondent,
          submission_report_id: bindSubmissionId || undefined,
        });
      } else if (onUploadSfr) {
        onUploadSfr(f);
      }
    }
  }

  return (
    <div className="response-review-panel">
      <p className="hint">
        Несколько подач и несколько входящих ответов (СФР и другие органы). Новый
        ответ — новая строка. Ответ органа ≠ выплата. Счёт 8 000 ₽ не создаётся
        автоматически.
      </p>

      {clientReportedWithoutDoc ? (
        <p className="hint" style={{ borderLeft: "3px solid #c45", paddingLeft: "0.5rem" }}>
          Клиент сообщил об ответе без файла — запросите документ.
          {onFollowUpControl ? (
            <>
              {" "}
              <button
                type="button"
                className="linkish"
                disabled={locked}
                onClick={() =>
                  void onFollowUpControl({
                    kind: "check",
                    check_result: "client_reported_response",
                    idempotency_key: `client_msg:${new Date().toISOString().slice(0, 10)}`,
                  })
                }
              >
                В контроль
              </button>
            </>
          ) : null}
        </p>
      ) : null}

      <h3 className="case-subhead">Матрица: подача ↔ ответ</h3>
      <table className="plain-table" style={{ width: "100%", fontSize: "0.9rem" }}>
        <thead>
          <tr>
            <th align="left">Подача</th>
            <th align="left">Файл</th>
            <th align="left">Орган</th>
            <th align="left">Статус</th>
            <th align="left"> </th>
          </tr>
        </thead>
        <tbody>
          {matrix.length === 0 ? (
            <tr>
              <td colSpan={5}>
                <span className="hint">Пока нет подач и файлов ответов.</span>
              </td>
            </tr>
          ) : (
            matrix.map((row) => (
              <tr
                key={row.key}
                style={
                  row.review?.id && row.review.id === selected?.id
                    ? { background: "rgba(0,0,0,0.04)" }
                    : undefined
                }
              >
                <td>{row.submissionLabel}</td>
                <td>
                  {row.file && onOpenDoc ? (
                    <button
                      type="button"
                      className="linkish"
                      onClick={() => onOpenDoc(row.file!.id)}
                    >
                      {row.fileLabel}
                    </button>
                  ) : (
                    row.fileLabel
                  )}
                </td>
                <td>{row.organ}</td>
                <td>{row.status}</td>
                <td>
                  {row.review?.id ? (
                    <button
                      type="button"
                      className="linkish"
                      disabled={working}
                      onClick={() => setSelectedId(row.review!.id || "")}
                    >
                      Открыть
                    </button>
                  ) : row.file ? (
                    <button
                      type="button"
                      className="linkish"
                      disabled={locked}
                      onClick={() =>
                        void registerFile(
                          row.file!.id,
                          row.submissionId || bindSubmissionId || undefined,
                        )
                      }
                    >
                      Зарегистрировать
                    </button>
                  ) : (
                    <span className="hint">загрузите файл ↓</span>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      <div className="row-actions" style={{ flexWrap: "wrap", gap: "0.5rem", marginTop: "0.75rem" }}>
        <label>
          Орган
          <select
            value={respondent}
            disabled={locked}
            onChange={(e) => {
              setRespondent(e.target.value);
              setUploadDocType(e.target.value === "sfr" ? "sfr_decision" : "agency_response");
            }}
          >
            {RESPONDENT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Подача для привязки
          <select
            value={bindSubmissionId}
            disabled={locked}
            onChange={(e) => setBindSubmissionId(e.target.value)}
          >
            <option value="">— не выбрано —</option>
            {submissionReports.map((r) => (
              <option key={r.id} value={r.id || ""}>
                {submissionLabel(r)}
              </option>
            ))}
          </select>
        </label>
        {(onUploadIncoming || onUploadSfr) && (
          <label className="secondary" style={{ display: "inline-block", padding: "0.35rem 0.6rem" }}>
            Загрузить ответ
            <input
              type="file"
              multiple
              hidden
              disabled={locked}
              onChange={(e) => {
                if (e.target.files?.length) handleUpload(e.target.files);
                e.target.value = "";
              }}
            />
          </label>
        )}
        <label>
          Файл без разбора → зарегистрировать
          <select
            value={bindDocId}
            disabled={locked || sfrDocuments.length === 0}
            onChange={(e) => setBindDocId(e.target.value)}
          >
            {sfrDocuments.length === 0 ? (
              <option value="">нет файлов</option>
            ) : (
              sfrDocuments.map((d) => (
                <option key={d.id} value={d.id}>
                  {incomingDocLabel(d)}
                </option>
              ))
            )}
          </select>
        </label>
        <button
          type="button"
          className="secondary"
          disabled={locked || !bindDocId}
          onClick={() => void registerFile(bindDocId, bindSubmissionId || undefined)}
        >
          Привязать файл
        </button>
        <button
          type="button"
          className="secondary"
          disabled={locked || sfrDocuments.length === 0}
          onClick={() => void extractAmounts()}
        >
          Извлечь черновик сумм
        </button>
      </div>

      {sfrDocuments.length > 0 ? (
        <div className="hint" style={{ marginTop: "0.5rem" }}>
          Файлы для разбора:{" "}
          {sfrDocuments.map((d) => {
            const checked = selectedDocIds.includes(d.id);
            return (
              <label key={d.id} style={{ marginRight: "0.75rem", display: "inline-block" }}>
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={locked}
                  onChange={(e) => {
                    setSelectedDocIds((prev) =>
                      e.target.checked
                        ? [...prev, d.id]
                        : prev.filter((x) => x !== d.id),
                    );
                  }}
                />{" "}
                {incomingDocLabel(d)}
                {d.created_at ? ` · ${(d.created_at || "").slice(0, 10)}` : ""}
                {d.ingest_status ? ` · OCR:${d.ingest_status}` : ""}
              </label>
            );
          })}
        </div>
      ) : null}

      {(chronology.length > 0 || amountsQuote || amountsWarnings.length > 0) && (
        <>
          <h3 className="case-subhead">Хронология сумм</h3>
          <p className="hint">
            Дата действия изменения (не дата файла). Начислено ≠ выплачено. Пусто = «Не
            указано», не ноль.
          </p>
          {amountsWarnings.length > 0 ? (
            <p className="hint" style={{ borderLeft: "3px solid #c45", paddingLeft: "0.5rem" }}>
              {amountsWarnings.join(" · ")}
            </p>
          ) : null}
          {amountsQuote ? (
            <p className="hint">
              Общая цитата: <em>{amountsQuote}</em>
            </p>
          ) : null}
          <table className="plain-table" style={{ width: "100%", fontSize: "0.85rem" }}>
            <thead>
              <tr>
                <th align="left">Дата действия</th>
                <th align="left">Документ / стр.</th>
                <th align="left">Было, ₽/мес.</th>
                <th align="left">Стало, ₽/мес.</th>
                <th align="left">Единовр., ₽</th>
                <th align="left">Основание и статус</th>
              </tr>
            </thead>
            <tbody>
              {chronology.map((row, i) => (
                <tr key={`${row.filename}-${i}`}>
                  <td>
                    {(row.effective_date || row.date || "не указана").toString().slice(0, 10)}
                  </td>
                  <td>
                    {row.filename || "—"}
                    {row.page ? `, стр. ${row.page}` : ""}
                  </td>
                  <td>{fmtAmt(row.monthly_before_rub)}</td>
                  <td>{fmtAmt(row.monthly_after_rub)}</td>
                  <td>{fmtAmt(row.lump_sum_rub)}</td>
                  <td>
                    {[
                      row.amount_kind || "",
                      row.payment_status || "",
                      row.basis_quote || row.note || "",
                    ]
                      .filter(Boolean)
                      .join(" · ") || "—"}
                    {row.conflict_group ? ` · конфликт:${row.conflict_group}` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {selected ? (
        <>
          <h3 className="case-subhead">
            Карточка ответа · {selected.respondent_label || selected.respondent || "СФР"} ·{" "}
            {STATUS_LABELS[selected.status || ""] || selected.status}
          </h3>
          <p className="hint">
            Файл:{" "}
            {selected.document_id && onOpenDoc ? (
              <button
                type="button"
                className="linkish"
                onClick={() => onOpenDoc(selected.document_id!)}
              >
                {(selected.document_id || "").slice(0, 8)}…
              </button>
            ) : (
              "—"
            )}
            {selected.sent_at
              ? ` · отправлено (${selected.sent_channel})`
              : " · клиенту ещё не отправлено"}
          </p>
          <div className="row-actions">
            <button type="button" disabled={locked} onClick={() => void aiDraft()}>
              Разобрать с ИИ
            </button>
            <button type="button" className="secondary" disabled={locked} onClick={() => void saveDraft()}>
              Сохранить правки
            </button>
            <button
              type="button"
              disabled={locked || !draft.trim()}
              onClick={() => void markReviewed()}
            >
              Проверено сотрудником
            </button>
            <button type="button" className="secondary" disabled={locked} onClick={() => void downloadDocx()}>
              Word
            </button>
            <button
              type="button"
              className="linkish"
              disabled={!draft.trim()}
              onClick={() => onApplyChat(draft)}
            >
              В чат…
            </button>
          </div>
          {draft ? (
            <textarea
              className="draft"
              style={{ width: "100%", minHeight: "12rem", marginTop: "0.5rem" }}
              value={draft}
              disabled={locked}
              onChange={(e) => setDraft(e.target.value)}
              aria-label="Черновик разбора ответа"
            />
          ) : (
            <p className="hint">Нажмите «Разобрать с ИИ».</p>
          )}

          <h3 className="case-subhead">Срок из ответа → контроль ст.10</h3>
          <label>
            Цитата срока
            <input
              value={deadlineQuote}
              disabled={locked}
              onChange={(e) => setDeadlineQuote(e.target.value)}
            />
          </label>
          <div className="row-actions">
            <input
              placeholder="источник"
              value={deadlineSource}
              disabled={locked}
              onChange={(e) => setDeadlineSource(e.target.value)}
            />
            <input
              placeholder="стр."
              value={deadlinePage}
              disabled={locked}
              onChange={(e) => setDeadlinePage(e.target.value)}
            />
            <input
              type="datetime-local"
              value={controlLocal}
              disabled={locked}
              onChange={(e) => setControlLocal(e.target.value)}
            />
            <button
              type="button"
              className="secondary"
              disabled={locked || !deadlineQuote.trim() || !controlLocal}
              onClick={() => void applyDeadlineControl()}
            >
              Назначить контроль
            </button>
          </div>

          <h3 className="case-subhead">Отправка клиенту</h3>
          <div className="row-actions" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
            <input
              type="email"
              placeholder="Почта"
              value={emailTo}
              disabled={locked}
              onChange={(e) => setEmailTo(e.target.value)}
            />
            <button
              type="button"
              className="secondary"
              disabled={locked || selected.status !== "reviewed"}
              onClick={() => void sendEmail(false)}
            >
              Превью почты
            </button>
            <button
              type="button"
              disabled={locked || selected.status !== "reviewed"}
              onClick={() => void sendEmail(true)}
            >
              Отправить почтой
            </button>
            <button
              type="button"
              className="secondary"
              disabled={locked || selected.status !== "reviewed"}
              onClick={() => void sendYadisk(false)}
            >
              Превью Диска
            </button>
            <button
              type="button"
              disabled={locked || selected.status !== "reviewed"}
              onClick={() => void sendYadisk(true)}
            >
              На Диск
            </button>
          </div>

          <h3 className="case-subhead">Дальнейший путь</h3>
          <div className="row-actions" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
            {(
              ["need_docs", "offer_escalation", "close", "wait_client"] as const
            ).map((o) => (
              <button
                key={o}
                type="button"
                className={selected.outcome === o ? "primary" : "secondary"}
                disabled={locked || selected.status !== "reviewed"}
                onClick={() => void setOutcome(o)}
              >
                {OUTCOME_LABELS[o]}
              </button>
            ))}
          </div>
        </>
      ) : (
        <p className="hint">Выберите строку в матрице или зарегистрируйте файл.</p>
      )}

      {msg ? <p className="hint">{msg}</p> : null}
    </div>
  );
}
