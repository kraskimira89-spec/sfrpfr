"use client";

import { useEffect, useMemo, useState } from "react";
import type { FollowUpControlPayload } from "@/components/follow-up-stage-panel";
import type { SubmissionReportView } from "@/components/submission-stage-panel";

export type ResponseReviewView = {
  id?: string;
  document_id?: string | null;
  submission_report_id?: string | null;
  doc_date?: string | null;
  doc_number?: string | null;
  received_at?: string | null;
  source?: string | null;
  completeness?: string | null;
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

const SOURCE_LABELS: Record<string, string> = {
  cabinet: "Кабинет СФР",
  chat: "Чат",
  mail: "Почта",
  staff: "Сотрудник",
};

const COMPLETENESS_LABELS: Record<string, string> = {
  all_pages: "Все страницы получены",
  need_more_pages: "Нужны дополнительные страницы",
  unknown: "Полнота не проверена",
};

const STATUS_LABELS: Record<string, string> = {
  received: "Получен (ещё не разобран)",
  reviewing: "Идёт разбор",
  reviewed: "Разбор проверен сотрудником",
};

const OUTCOME_LABELS: Record<string, string> = {
  need_docs: "Нужны документы / пояснения",
  offer_escalation: "Предложить доп. обращения (ступень 12)",
  close: "Передать на завершение (ступень 13)",
  wait_client: "Клиент пока не решил",
};

type Props = {
  busy: boolean;
  token: string;
  apiBase: string;
  caseId: string;
  clientEmail?: string | null;
  reviews: ResponseReviewView[];
  submissionReports: SubmissionReportView[];
  sfrDocumentIds: string[];
  clientReportedWithoutDoc?: boolean;
  canEdit: boolean;
  onReload: () => Promise<void> | void;
  onUploadSfr?: (file: File) => void;
  onApplyChat: (text: string) => void;
  onFollowUpControl?: (payload: FollowUpControlPayload) => Promise<void> | void;
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

export function ResponseReviewPanel({
  busy,
  token,
  apiBase,
  caseId,
  clientEmail,
  reviews,
  submissionReports,
  sfrDocumentIds,
  clientReportedWithoutDoc,
  canEdit,
  onReload,
  onUploadSfr,
  onApplyChat,
  onFollowUpControl,
}: Props) {
  const [docId, setDocId] = useState(sfrDocumentIds[0] || "");
  const [submissionId, setSubmissionId] = useState(
    submissionReports[0]?.id || "",
  );
  const [source, setSource] = useState("staff");
  const [completeness, setCompleteness] = useState("unknown");
  const [docDate, setDocDate] = useState("");
  const [docNumber, setDocNumber] = useState("");
  const [deadlineQuote, setDeadlineQuote] = useState("");
  const [deadlineSource, setDeadlineSource] = useState("");
  const [deadlinePage, setDeadlinePage] = useState("");
  const [controlLocal, setControlLocal] = useState("");
  const [selectedId, setSelectedId] = useState(reviews[0]?.id || "");
  const [draft, setDraft] = useState("");
  const [emailTo, setEmailTo] = useState(clientEmail || "");
  const [msg, setMsg] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  const selected = useMemo(() => {
    const id = selectedId || reviews[0]?.id;
    return reviews.find((r) => r.id === id) || reviews[0] || null;
  }, [reviews, selectedId]);

  useEffect(() => {
    if (!selected) return;
    setDraft(String(selected.staff_draft_md || selected.ai_draft_md || ""));
    setDeadlineQuote(String(selected.deadline_quote || ""));
    setDeadlineSource(String(selected.deadline_quote_source || ""));
    setDeadlinePage(String(selected.deadline_quote_page || ""));
  }, [selected?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const base = `${apiBase}/api/portal/admin/cases/${caseId}/response-review`;
  const locked = busy || working || !canEdit;

  async function register() {
    if (!docId) {
      setMsg("Выберите файл ответа СФР");
      return;
    }
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
            source,
            completeness,
            doc_date: docDate || undefined,
            doc_number: docNumber || undefined,
            deadline_quote: deadlineQuote || undefined,
            deadline_quote_source: deadlineSource || undefined,
            deadline_quote_page: deadlinePage || undefined,
            idempotency_key: `register:${docId}:${submissionId || "none"}`,
          }),
        },
      );
      setMsg(
        out.replayed
          ? "Повтор: ответ уже зарегистрирован (без дубля)."
          : "Ответ зарегистрирован. Разбор ещё не выполнен.",
      );
      if (out.review?.id) setSelectedId(out.review.id);
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
    setMsg(null);
    try {
      const out = await apiJson<{ text?: string; reason?: string; source?: string }>(
        `${base}/${selected.id}/ai-draft`,
        token,
        { method: "POST", body: "{}" },
      );
      setDraft(String(out.text || ""));
      setMsg(
        out.source === "template"
          ? `Черновик-шаблон (${out.reason || "без ИИ"}) — проверьте вручную.`
          : "ИИ подготовил проект. Проверьте источники и правьте текст.",
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
      setMsg("Разбор отмечен как проверенный сотрудником.");
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
    a.download = `otvet-sfr.docx`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function sendEmail(confirm: boolean) {
    if (!selected?.id) return;
    setWorking(true);
    try {
      const out = await apiJson<{
        ok?: boolean;
        preview?: boolean;
        error?: string;
        subject?: string;
        body?: string;
      }>(`${base}/${selected.id}/send-email`, token, {
        method: "POST",
        body: JSON.stringify({ to: emailTo, confirm }),
      });
      if (out.preview && !confirm) {
        setMsg(
          `Превью письма → ${emailTo}. Подтвердите повторным нажатием «Отправить почтой».`,
        );
      } else if (out.ok) {
        setMsg("Письмо отправлено (проверенная версия).");
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
        setMsg("Превью Диска готово. Подтвердите «Отправить на Диск».");
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
        {
          method: "POST",
          body: JSON.stringify({ outcome }),
        },
      );
      setMsg(
        out.note ||
          `Дальнейшее действие: ${OUTCOME_LABELS[outcome] || outcome}. Счёт 8 000 ₽ не создан.`,
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
      const d = new Date(controlLocal);
      await apiJson(`${base}/${selected.id}/set-deadline-control`, token, {
        method: "POST",
        body: JSON.stringify({ control_at: d.toISOString() }),
      });
      setMsg("Контроль назначен через ступень 10 (next_action_at).");
      await onReload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Ошибка контроля");
    } finally {
      setWorking(false);
    }
  }

  return (
    <div className="response-review-panel">
      <p className="hint">
        Передача из ступени 10 открывает работу, но не означает, что ответ уже
        проверен. Сообщение клиента без файла — не документ СФР. Новый ответ
        сохраняется отдельно. Переход к ступени 12 не создаёт счёт 8 000 ₽.
        Положительный ответ СФР ≠ выплата.
      </p>

      {clientReportedWithoutDoc ? (
        <p className="hint" style={{ borderLeft: "3px solid #c45", paddingLeft: "0.5rem" }}>
          Клиент сообщил об ответе (например, «пришёл отказ») — это сообщение
          клиента, документа ещё нет. Запросите файл.
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
                Зафиксировать в контроле
              </button>
            </>
          ) : null}
        </p>
      ) : null}

      <h3 className="case-subhead">Регистрация ответа</h3>
      <label>
        Файл ответа СФР
        <select
          value={docId}
          disabled={locked || sfrDocumentIds.length === 0}
          onChange={(e) => setDocId(e.target.value)}
        >
          {sfrDocumentIds.length === 0 ? (
            <option value="">Нет файлов sfr_decision / sfr_response</option>
          ) : (
            sfrDocumentIds.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))
          )}
        </select>
      </label>
      <label>
        Связать с подачей (ступень 9)
        <select
          value={submissionId}
          disabled={locked}
          onChange={(e) => setSubmissionId(e.target.value)}
        >
          <option value="">— не выбрано —</option>
          {submissionReports.map((r) => (
            <option key={r.id} value={r.id || ""}>
              {(r.submitted_on || "?").slice(0, 10)} · {r.method || "?"} ·{" "}
              {(r.id || "").slice(0, 8)}
            </option>
          ))}
        </select>
      </label>
      <div className="row-actions" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
        <label>
          Источник
          <select value={source} disabled={locked} onChange={(e) => setSource(e.target.value)}>
            {Object.entries(SOURCE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label>
          Полнота
          <select
            value={completeness}
            disabled={locked}
            onChange={(e) => setCompleteness(e.target.value)}
          >
            {Object.entries(COMPLETENESS_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label>
          Дата документа
          <input type="date" value={docDate} disabled={locked} onChange={(e) => setDocDate(e.target.value)} />
        </label>
        <label>
          Номер
          <input value={docNumber} disabled={locked} onChange={(e) => setDocNumber(e.target.value)} />
        </label>
      </div>
      <div className="row-actions">
        <button type="button" disabled={locked || !docId} onClick={() => void register()}>
          Зарегистрировать ответ
        </button>
        {onUploadSfr ? (
          <label className="secondary" style={{ display: "inline-block", padding: "0.35rem 0.6rem" }}>
            Загрузить новый файл
            <input
              type="file"
              hidden
              disabled={locked}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onUploadSfr(f);
                e.target.value = "";
              }}
            />
          </label>
        ) : null}
      </div>

      {reviews.length > 0 ? (
        <>
          <h3 className="case-subhead">Сохранённые ответы</h3>
          <ul className="plain-list">
            {reviews.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  className={r.id === selected?.id ? "primary" : "linkish"}
                  disabled={working}
                  onClick={() => setSelectedId(r.id || "")}
                >
                  {(r.created_at || "").slice(0, 10) || "—"} ·{" "}
                  {STATUS_LABELS[r.status || ""] || r.status} ·{" "}
                  {(r.document_id || "").slice(0, 8)}
                  {r.outcome ? ` → ${OUTCOME_LABELS[r.outcome] || r.outcome}` : ""}
                </button>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="hint">Зарегистрированных ответов пока нет.</p>
      )}

      {selected ? (
        <>
          <h3 className="case-subhead">Разбор с ИИ</h3>
          <p className="hint">
            Статус: <strong>{STATUS_LABELS[selected.status || ""] || selected.status}</strong>
            {selected.sent_at
              ? ` · отправлено (${selected.sent_channel || "?"})`
              : " · клиенту ещё не отправлено"}
            {" · "}
            полнота: {COMPLETENESS_LABELS[selected.completeness || ""] || selected.completeness}
          </p>
          <div className="row-actions">
            <button type="button" disabled={locked} onClick={() => void aiDraft()}>
              Разобрать ответ СФР с ИИ
            </button>
            <button type="button" className="secondary" disabled={locked} onClick={() => void saveDraft()}>
              Сохранить правки
            </button>
            <button
              type="button"
              disabled={locked || !draft.trim()}
              onClick={() => void markReviewed()}
              title="Без отметки отправка недоступна"
            >
              Проверено сотрудником
            </button>
            <button type="button" className="secondary" disabled={locked} onClick={() => void downloadDocx()}>
              Скачать Word
            </button>
            <button
              type="button"
              className="linkish"
              disabled={!draft.trim()}
              onClick={() => onApplyChat(draft)}
            >
              Текст в чат…
            </button>
          </div>
          {draft ? (
            <textarea
              className="draft"
              style={{ width: "100%", minHeight: "14rem", marginTop: "0.5rem" }}
              value={draft}
              disabled={locked}
              onChange={(e) => setDraft(e.target.value)}
              aria-label="Черновик разбора ответа СФР"
            />
          ) : (
            <p className="hint">Нажмите «Разобрать ответ СФР с ИИ». Непроверенный текст клиенту не уходит.</p>
          )}

          <h3 className="case-subhead">Срок из ответа (проверка сотрудником)</h3>
          <p className="hint">
            Универсальный срок обжалования не назначаем. Контроль — через механизм ступени 10.
          </p>
          <label>
            Точный текст срока
            <input
              value={deadlineQuote}
              disabled={locked}
              onChange={(e) => setDeadlineQuote(e.target.value)}
              placeholder="цитата из ответа"
            />
          </label>
          <div className="row-actions">
            <label>
              Источник
              <input
                value={deadlineSource}
                disabled={locked}
                onChange={(e) => setDeadlineSource(e.target.value)}
                placeholder="п. / абзац"
              />
            </label>
            <label>
              Стр.
              <input
                value={deadlinePage}
                disabled={locked}
                onChange={(e) => setDeadlinePage(e.target.value)}
              />
            </label>
            <label>
              Контрольная дата
              <input
                type="datetime-local"
                value={controlLocal}
                disabled={locked}
                onChange={(e) => setControlLocal(e.target.value)}
              />
            </label>
            <button
              type="button"
              className="secondary"
              disabled={locked || !deadlineQuote.trim() || !controlLocal}
              onClick={() => void applyDeadlineControl()}
            >
              Назначить контроль из срока
            </button>
          </div>

          <h3 className="case-subhead">Отправка клиенту</h3>
          <p className="hint">Сначала превью, затем подтверждение. Уходит только проверенная версия.</p>
          <div className="row-actions" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
            <input
              type="email"
              placeholder="Почта клиента"
              value={emailTo}
              disabled={locked}
              onChange={(e) => setEmailTo(e.target.value)}
              style={{ minWidth: "14rem" }}
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
              Отправить на Диск
            </button>
          </div>

          <h3 className="case-subhead">Дальнейший путь</h3>
          <div className="row-actions" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
            {(
              [
                "need_docs",
                "offer_escalation",
                "close",
                "wait_client",
              ] as const
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
      ) : null}

      {msg ? <p className="hint">{msg}</p> : null}
    </div>
  );
}
