"use client";

import { useState } from "react";

export type SubmissionReportView = {
  kind?: string;
  submitted_on?: string | null;
  method?: string | null;
  submitted_what?: string | null;
  source?: string | null;
  appeal_number?: string | null;
  proof_document_id?: string | null;
  proof_missing?: boolean;
  proof_missing_note?: string | null;
  package_version?: string | null;
  comment?: string | null;
  actor_kind?: string | null;
  created_at?: string | null;
};

export type SubmissionFormPayload = {
  decision: "confirmed" | "help_requested" | "receipt_verified";
  submitted_on?: string;
  method?: string;
  submitted_what?: string;
  appeal_number?: string;
  proof_document_id?: string;
  comment?: string;
  source?: string;
  idempotency_key?: string;
  package_version?: string;
};

const METHOD_LABELS: Record<string, string> = {
  gosuslugi: "Госуслуги",
  sfr: "Лично в СФР",
  mfc: "МФЦ",
  post: "Почта",
  other: "Другое",
};

const SOURCE_LABELS: Record<string, string> = {
  client_self: "Клиент в кабинете",
  client_words: "Со слов клиента",
};

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function SubmissionStagePanel({
  busy,
  packageDelivered,
  submissionConfirmed,
  receiptVerified,
  report,
  defaultPackageLabel,
  onSubmit,
  onAskChat,
}: {
  busy: boolean;
  packageDelivered: boolean;
  submissionConfirmed: boolean;
  receiptVerified: boolean;
  report: SubmissionReportView | null | undefined;
  defaultPackageLabel: string;
  onSubmit: (payload: SubmissionFormPayload) => void;
  onAskChat: () => void;
}) {
  const [submittedOn, setSubmittedOn] = useState(todayIso());
  const [method, setMethod] = useState("gosuslugi");
  const [submittedWhat, setSubmittedWhat] = useState(defaultPackageLabel || "Пакет первичных обращений");
  const [appealNumber, setAppealNumber] = useState("");
  const [proofId, setProofId] = useState("");
  const [comment, setComment] = useState("");

  const canForm = packageDelivered && !busy;

  return (
    <div className="submission-stage-panel">
      <p className="hint">
        Передача пакета ≠ подача в СФР. Мы готовим документы и план — подаёте через СФР, МФЦ или
        Госуслуги вы сами. Решение о пенсии принимает только СФР.
      </p>

      {report && report.kind === "client_reported" ? (
        <div className="submission-report-card" style={{ marginBottom: "0.75rem" }}>
          <p>
            <strong>Клиент сообщил о подаче</strong>
            {report.proof_missing ? (
              <>
                {" "}
                · <em>{report.proof_missing_note}</em>
              </>
            ) : (
              " · подтверждение приёма приложено"
            )}
          </p>
          <ul className="hint" style={{ margin: 0, paddingLeft: "1.2rem" }}>
            <li>Дата: {report.submitted_on || "—"}</li>
            <li>Способ: {METHOD_LABELS[String(report.method || "")] || report.method || "—"}</li>
            <li>Состав: {report.submitted_what || "—"}</li>
            <li>
              Источник: {SOURCE_LABELS[String(report.source || "")] || report.source || "—"}
              {report.actor_kind ? ` (${report.actor_kind})` : ""}
            </li>
            {report.package_version ? <li>Пакет: {report.package_version}</li> : null}
            {report.appeal_number ? <li>№ обращения: {report.appeal_number}</li> : null}
            {report.proof_document_id ? <li>Файл: {report.proof_document_id}</li> : null}
            {report.comment ? <li>Комментарий: {report.comment}</li> : null}
            {report.created_at ? <li>Запись: {report.created_at}</li> : null}
          </ul>
          {receiptVerified ? (
            <p className="hint">Подтверждение приёма проверено сотрудником (отдельный факт).</p>
          ) : (
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => onSubmit({ decision: "receipt_verified" })}
            >
              Подтверждение приёма проверено
            </button>
          )}
        </div>
      ) : null}

      {!packageDelivered ? (
        <p className="hint">Сначала зафиксируйте передачу пакета клиенту (ступень 8).</p>
      ) : null}

      {canForm && !submissionConfirmed ? (
        <div className="submission-form" style={{ display: "grid", gap: "0.4rem", maxWidth: 420 }}>
          <p className="hint">Запись со слов клиента (источник фиксируется автоматически).</p>
          <label>
            Дата подачи
            <input
              type="date"
              value={submittedOn}
              max={todayIso()}
              onChange={(e) => setSubmittedOn(e.target.value)}
              disabled={busy}
            />
          </label>
          <label>
            Способ
            <select value={method} onChange={(e) => setMethod(e.target.value)} disabled={busy}>
              {Object.entries(METHOD_LABELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label>
            Что подано
            <input
              type="text"
              value={submittedWhat}
              onChange={(e) => setSubmittedWhat(e.target.value)}
              disabled={busy}
            />
          </label>
          <label>
            № обращения (необязательно)
            <input
              type="text"
              value={appealNumber}
              onChange={(e) => setAppealNumber(e.target.value)}
              disabled={busy}
            />
          </label>
          <label>
            ID подтверждающего файла (необязательно)
            <input
              type="text"
              value={proofId}
              onChange={(e) => setProofId(e.target.value)}
              disabled={busy}
              placeholder="document id"
            />
          </label>
          <label>
            Комментарий
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              disabled={busy}
              rows={2}
            />
          </label>
          <div className="row-actions">
            <button
              type="button"
              className="primary"
              disabled={busy || !submittedOn || !submittedWhat.trim()}
              onClick={() =>
                onSubmit({
                  decision: "confirmed",
                  submitted_on: submittedOn,
                  method,
                  submitted_what: submittedWhat.trim(),
                  appeal_number: appealNumber.trim() || undefined,
                  proof_document_id: proofId.trim() || undefined,
                  comment: comment.trim() || undefined,
                  source: "client_words",
                  package_version: defaultPackageLabel || undefined,
                  idempotency_key: `staff:${submittedOn}:${method}:${submittedWhat.trim()}`,
                })
              }
            >
              Сохранить: со слов клиента подал
            </button>
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() =>
                onSubmit({
                  decision: "help_requested",
                  comment: comment.trim() || undefined,
                  source: "client_words",
                })
              }
            >
              Нужна помощь с подачей
            </button>
          </div>
        </div>
      ) : null}

      <div className="row-actions">
        <button type="button" className="secondary" disabled={busy} onClick={onAskChat}>
          Спросить: сам / нужен звонок
        </button>
      </div>
    </div>
  );
}
