"use client";

import { useState } from "react";

export type ClientSubmissionReport = {
  kind?: string;
  submitted_on?: string | null;
  method?: string | null;
  submitted_what?: string | null;
  proof_missing?: boolean;
  proof_missing_note?: string | null;
};

const METHOD_OPTIONS: { value: string; label: string }[] = [
  { value: "gosuslugi", label: "Госуслуги" },
  { value: "sfr", label: "Лично в СФР" },
  { value: "mfc", label: "МФЦ" },
  { value: "post", label: "Почта" },
  { value: "other", label: "Другое" },
];

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function SubmissionClientPanel({
  busy,
  packageDelivered,
  report,
  defaultWhat,
  onConfirm,
  onHelp,
}: {
  busy: boolean;
  packageDelivered: boolean;
  report: ClientSubmissionReport | null | undefined;
  defaultWhat: string;
  onConfirm: (payload: {
    submitted_on: string;
    method: string;
    submitted_what: string;
    appeal_number?: string;
    comment?: string;
    idempotency_key?: string;
  }) => void;
  onHelp: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [submittedOn, setSubmittedOn] = useState(todayIso());
  const [method, setMethod] = useState("gosuslugi");
  const [submittedWhat, setSubmittedWhat] = useState(defaultWhat);
  const [appealNumber, setAppealNumber] = useState("");
  const [comment, setComment] = useState("");

  if (!packageDelivered) return null;

  if (report?.kind === "client_reported") {
    return (
      <div className="panel" style={{ marginTop: "0.75rem" }}>
        <h2>Подача документов</h2>
        <p className="ok">Вы сообщили о подаче{report.submitted_on ? ` (${report.submitted_on})` : ""}.</p>
        {report.proof_missing ? (
          <p className="hint">{report.proof_missing_note}</p>
        ) : null}
      </div>
    );
  }

  if (report?.kind === "help_requested") {
    return (
      <div className="panel" style={{ marginTop: "0.75rem" }}>
        <h2>Подача документов</h2>
        <p>Запрос помощи с подачей отправлен специалисту. Ответ смотрите в переписке справа.</p>
      </div>
    );
  }

  return (
    <div className="panel accent" style={{ marginTop: "0.75rem" }}>
      <h2>Подайте документы в СФР</h2>
      <p>
        Подготовленный пакет доступен в вашем деле. После подачи сообщите дату и способ —
        специалист сможет отслеживать дальнейшие действия.
      </p>
      {!open ? (
        <p style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "0.75rem" }}>
          <button type="button" disabled={busy} onClick={() => setOpen(true)}>
            Я подал документы
          </button>
          <button type="button" className="ghost" disabled={busy} onClick={onHelp}>
            Нужна помощь с подачей
          </button>
        </p>
      ) : (
        <div className="stack" style={{ marginTop: "0.75rem", gap: "0.5rem" }}>
          <label>
            Дата подачи
            <input
              type="date"
              value={submittedOn}
              max={todayIso()}
              disabled={busy}
              onChange={(e) => setSubmittedOn(e.target.value)}
            />
          </label>
          <label>
            Способ
            <select value={method} disabled={busy} onChange={(e) => setMethod(e.target.value)}>
              {METHOD_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Что подано
            <input
              type="text"
              value={submittedWhat}
              disabled={busy}
              onChange={(e) => setSubmittedWhat(e.target.value)}
            />
          </label>
          <label>
            № обращения (необязательно)
            <input
              type="text"
              value={appealNumber}
              disabled={busy}
              onChange={(e) => setAppealNumber(e.target.value)}
            />
          </label>
          <label>
            Комментарий (необязательно)
            <textarea
              rows={2}
              value={comment}
              disabled={busy}
              onChange={(e) => setComment(e.target.value)}
            />
          </label>
          <p className="hint">
            Подтверждающий файл необязателен. Без него сохраним: «Клиент сообщил о подаче;
            подтверждение приёма не приложено».
          </p>
          <p style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
            <button
              type="button"
              disabled={busy || !submittedOn || !submittedWhat.trim()}
              onClick={() =>
                onConfirm({
                  submitted_on: submittedOn,
                  method,
                  submitted_what: submittedWhat.trim(),
                  appeal_number: appealNumber.trim() || undefined,
                  comment: comment.trim() || undefined,
                  idempotency_key: `client:${submittedOn}:${method}:${submittedWhat.trim()}`,
                })
              }
            >
              Сохранить
            </button>
            <button type="button" className="ghost" disabled={busy} onClick={() => setOpen(false)}>
              Отмена
            </button>
          </p>
        </div>
      )}
    </div>
  );
}
