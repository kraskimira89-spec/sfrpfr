"use client";

import { useMemo, useState } from "react";
import type { SubmissionReportView } from "@/components/submission-stage-panel";
import {
  FOLLOW_UP_UI_LABELS,
  deriveFollowUpUiState,
  type FollowUpUiState,
} from "@/lib/follow-up-control";

export type FollowUpEventView = {
  id?: string;
  kind?: string;
  check_result?: string | null;
  control_at?: string | null;
  previous_control_at?: string | null;
  created_at?: string | null;
  next_action_text?: string | null;
  reason?: string | null;
  actor_id?: string | null;
  document_id?: string | null;
};

export type FollowUpControlPayload = {
  kind: "assign_control" | "check" | "reschedule" | "response_handoff";
  control_at?: string;
  next_action_text?: string;
  reason?: string;
  check_result?: "no_response" | "need_more_info" | "client_reported_response";
  waiting_on?: string;
  expert_user_id?: string;
  document_id?: string;
  idempotency_key?: string;
};

const METHOD_LABELS: Record<string, string> = {
  gosuslugi: "Госуслуги",
  sfr: "Лично в СФР",
  mfc: "МФЦ",
  post: "Почта",
  other: "Другое",
};

const SOURCE_LABELS: Record<string, string> = {
  client_self: "Клиент сообщил",
  client_words: "Сотрудник записал со слов клиента",
};

const CHECK_LABELS: Record<string, string> = {
  no_response: "Ответа нет",
  need_more_info: "Нужны дополнительные сведения",
  client_reported_response: "Клиент сообщил об ответе — запросить документ",
};

const KIND_LABELS: Record<string, string> = {
  assign_control: "Назначен контроль",
  check: "Проверка",
  reschedule: "Перенос",
  response_handoff: "Ответ передан на разбор",
};

function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromLocalInput(local: string): string {
  // datetime-local → ISO; сервер хранит timestamptz
  const d = new Date(local);
  return d.toISOString();
}

export function FollowUpStagePanel({
  busy,
  submissionConfirmed,
  followUpCompleted,
  responseReceived,
  receiptVerified,
  report,
  controlAt,
  nextAction,
  expertUserId,
  meUserId,
  events,
  sfrDocuments = [],
  onControl,
  onUploadSfr,
}: {
  busy: boolean;
  submissionConfirmed: boolean;
  followUpCompleted: boolean;
  responseReceived: boolean;
  receiptVerified: boolean;
  report: SubmissionReportView | null | undefined;
  controlAt: string | null | undefined;
  nextAction: string | null | undefined;
  expertUserId: string | null | undefined;
  meUserId: string | null;
  events: FollowUpEventView[];
  /** Входящие ответы (СФР / иное) — показываем имена, не UUID. */
  sfrDocuments?: { id: string; label: string }[];
  onControl: (payload: FollowUpControlPayload) => void;
  onUploadSfr?: (file: File) => void;
}) {
  const sfrDocumentIds = sfrDocuments.map((d) => d.id);
  const uiState: FollowUpUiState = deriveFollowUpUiState({
    submissionConfirmed,
    followUpCompleted,
    responseReceived,
    controlAt,
  });

  const [controlLocal, setControlLocal] = useState(toLocalInput(controlAt) || "");
  const [actionText, setActionText] = useState(
    nextAction || "Уточнить у клиента, поступил ли ответ",
  );
  const [rescheduleReason, setRescheduleReason] = useState("");
  const [checkResult, setCheckResult] = useState<
    "no_response" | "need_more_info" | "client_reported_response"
  >("no_response");
  const [handoffDocId, setHandoffDocId] = useState(sfrDocumentIds[0] || "");

  const lastCheck = useMemo(
    () => events.find((e) => e.kind === "check") || null,
    [events],
  );

  const canAct = submissionConfirmed && !busy && uiState !== "done";

  return (
    <div className="follow-up-stage-panel">
      <p className="hint">
        Контрольная дата — внутренняя проверка дела, не обещанный срок решения СФР. Часовой пояс
        календаря: UTC+5 (Asia/Yekaterinburg).
      </p>
      <p>
        <strong>{FOLLOW_UP_UI_LABELS[uiState]}</strong>
        {uiState === "overdue_internal" ? (
          <span className="hint"> — это не «СФР отказал» и не нарушение срока фонда.</span>
        ) : null}
      </p>

      <div style={{ marginBottom: "0.75rem" }}>
        <p>
          <strong>Сведения о подаче</strong>
        </p>
        {report && report.kind === "client_reported" ? (
          <ul className="hint" style={{ margin: 0, paddingLeft: "1.2rem" }}>
            <li>Дата: {report.submitted_on || "—"}</li>
            <li>Способ: {METHOD_LABELS[String(report.method || "")] || report.method || "—"}</li>
            <li>Состав: {report.submitted_what || "—"}</li>
            {report.appeal_number ? <li>№ обращения: {report.appeal_number}</li> : null}
            <li>
              Источник: {SOURCE_LABELS[String(report.source || "")] || report.source || "—"}
            </li>
            <li>
              Подтверждение приёма:{" "}
              {receiptVerified
                ? "проверено сотрудником"
                : report.proof_missing
                  ? report.proof_missing_note || "не приложено"
                  : "файл есть, проверка отдельно"}
            </li>
          </ul>
        ) : (
          <p className="hint">Нет структурированного отчёта о подаче — контроль всё равно можно вести.</p>
        )}
      </div>

      <p className="hint">
        Ответственный: {expertUserId || "не назначен"}
        {meUserId ? ` · вы: ${meUserId}` : ""}
      </p>
      <p className="hint">
        Контроль: {controlAt || "—"} · действие: {nextAction || "—"}
      </p>
      {lastCheck ? (
        <p className="hint">
          Последняя проверка: {lastCheck.created_at || "—"} ·{" "}
          {CHECK_LABELS[String(lastCheck.check_result || "")] || lastCheck.check_result || "—"}
          {lastCheck.actor_id ? ` · ${lastCheck.actor_id}` : ""}
        </p>
      ) : null}

      {canAct ? (
        <div className="stack" style={{ display: "grid", gap: "0.4rem", maxWidth: 480 }}>
          <label>
            Контрольная дата
            <input
              type="datetime-local"
              value={controlLocal}
              disabled={busy}
              onChange={(e) => setControlLocal(e.target.value)}
            />
          </label>
          <label>
            Следующее действие
            <input
              type="text"
              value={actionText}
              disabled={busy}
              onChange={(e) => setActionText(e.target.value)}
            />
          </label>
          <div className="row-actions">
            <button
              type="button"
              className="primary"
              disabled={busy || !controlLocal || !actionText.trim()}
              onClick={() =>
                onControl({
                  kind: "assign_control",
                  control_at: fromLocalInput(controlLocal),
                  next_action_text: actionText.trim(),
                  expert_user_id: expertUserId || meUserId || undefined,
                  waiting_on: "sfr",
                  idempotency_key: `assign:${controlLocal}:${actionText.trim()}`,
                })
              }
            >
              Назначить контроль
            </button>
          </div>

          <label>
            Результат проверки
            <select
              value={checkResult}
              disabled={busy}
              onChange={(e) =>
                setCheckResult(
                  e.target.value as
                    | "no_response"
                    | "need_more_info"
                    | "client_reported_response",
                )
              }
            >
              {Object.entries(CHECK_LABELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="secondary"
            disabled={busy || !controlAt}
            onClick={() =>
              onControl({
                kind: "check",
                check_result: checkResult,
                next_action_text:
                  checkResult === "client_reported_response"
                    ? CHECK_LABELS.client_reported_response
                    : actionText.trim() || undefined,
                idempotency_key: `check:${checkResult}:${new Date().toISOString().slice(0, 13)}`,
              })
            }
          >
            Зафиксировать проверку
          </button>

          <label>
            Причина переноса
            <input
              type="text"
              value={rescheduleReason}
              disabled={busy}
              onChange={(e) => setRescheduleReason(e.target.value)}
              placeholder="Почему переносим"
            />
          </label>
          <button
            type="button"
            className="secondary"
            disabled={busy || !controlLocal || !rescheduleReason.trim()}
            onClick={() =>
              onControl({
                kind: "reschedule",
                control_at: fromLocalInput(controlLocal),
                reason: rescheduleReason.trim(),
                next_action_text: actionText.trim() || undefined,
                idempotency_key: `reschedule:${controlLocal}:${rescheduleReason.trim()}`,
              })
            }
          >
            Перенести контроль
          </button>

          <label>
            Входящий ответ (уже загруженный)
            <select
              value={handoffDocId}
              disabled={busy || sfrDocuments.length === 0}
              onChange={(e) => setHandoffDocId(e.target.value)}
            >
              {sfrDocuments.length === 0 ? (
                <option value="">Нет файлов ответа</option>
              ) : (
                sfrDocuments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.label}
                  </option>
                ))
              )}
            </select>
          </label>
          <div className="row-actions">
            <button
              type="button"
              className="primary"
              disabled={busy || !handoffDocId}
              onClick={() =>
                onControl({
                  kind: "response_handoff",
                  document_id: handoffDocId,
                  next_action_text: "Разбор ответа СФР (ступень 11)",
                  idempotency_key: `handoff:${handoffDocId}`,
                })
              }
            >
              Добавить ответ СФР → ступень 11
            </button>
            {onUploadSfr ? (
              <label className="secondary" style={{ display: "inline-block", padding: "0.35rem 0.6rem" }}>
                Загрузить файл ответа
                <input
                  type="file"
                  hidden
                  disabled={busy}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) onUploadSfr(f);
                    e.target.value = "";
                  }}
                />
              </label>
            ) : null}
          </div>
        </div>
      ) : null}

      {events.length > 0 ? (
        <div style={{ marginTop: "0.75rem" }}>
          <p>
            <strong>История контроля</strong>
          </p>
          <ul className="hint" style={{ margin: 0, paddingLeft: "1.2rem" }}>
            {events.slice(0, 12).map((e) => (
              <li key={e.id || `${e.kind}-${e.created_at}`}>
                {e.created_at || "—"} · {KIND_LABELS[String(e.kind || "")] || e.kind}
                {e.check_result
                  ? ` · ${CHECK_LABELS[String(e.check_result)] || e.check_result}`
                  : ""}
                {e.control_at ? ` · до ${e.control_at}` : ""}
                {e.reason ? ` · ${e.reason}` : ""}
                {e.previous_control_at ? ` (было ${e.previous_control_at})` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
