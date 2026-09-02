"use client";

import { useCallback, useEffect, useState } from "react";

type NotificationJob = {
  id: string;
  job_type: string;
  channel: string;
  status: string;
  subject?: string | null;
  body?: string | null;
  created_at?: string;
  scheduled_at?: string | null;
};

type SurveyCampaign = {
  id: string;
  survey_type: string;
  channel: string;
  status: string;
  scheduled_at?: string | null;
  sent_at?: string | null;
  completed_at?: string | null;
  touch_index?: number | null;
  body?: string | null;
};

type DiagnosisFeedback = {
  pdf_issued_at?: string | null;
  pdf_opened_at?: string | null;
  feedback_status?: string | null;
  clarity_score?: number | null;
  first_plan_step_status?: string | null;
  touch2_due_at?: string | null;
  touch3_due_at?: string | null;
  touch2_sent_at?: string | null;
  touch3_sent_at?: string | null;
};

type MaxAttachment = {
  type: string;
  payload?: { buttons?: { type: string; text: string; payload: string }[][] };
};

type ApproveSurveyResult = {
  ok?: boolean;
  body?: string;
  attachments?: MaxAttachment[];
  email_links?: { answer_code: string; label: string; url: string }[];
  cancelled?: boolean;
  reason?: string;
};

const SURVEY_LABELS: Record<string, string> = {
  clarity: "Понятность (2–3 дн.)",
  acquaint: "Ознакомление",
  first_step: "Первый шаг (10–14 дн.)",
  quality: "Качество услуги",
};

const STATUS_LABELS: Record<string, string> = {
  draft: "черновик",
  scheduled: "запланирован",
  approved: "подтверждён",
  sent: "отправлен",
  completed: "завершён",
  cancelled: "отменён",
  failed: "ошибка",
  queued: "в очереди",
  delivered: "доставлен",
};

function fmtDate(iso?: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ru-RU", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

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
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const raw = (await response.text()) || `HTTP ${response.status}`;
    throw new Error(raw.slice(0, 200));
  }
  return response.json() as Promise<T>;
}

export function DiagnosisDeliveryPanel({
  caseId,
  token,
  apiBase,
  clientEmail,
  busy,
  onNotice,
  onRefresh,
}: {
  caseId: string;
  token: string;
  apiBase: string;
  clientEmail?: string | null;
  busy: boolean;
  onNotice: (msg: string) => void;
  onRefresh: () => void;
}) {
  const [loading, setLoading] = useState(true);
  const [feedback, setFeedback] = useState<DiagnosisFeedback | null>(null);
  const [jobs, setJobs] = useState<NotificationJob[]>([]);
  const [campaigns, setCampaigns] = useState<SurveyCampaign[]>([]);
  const [surveyDraft, setSurveyDraft] = useState<ApproveSurveyResult | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [fb, nj, sc] = await Promise.all([
        staffFetch<{ feedback: DiagnosisFeedback | null }>(
          apiBase,
          `/api/portal/admin/cases/${caseId}/diagnosis-feedback`,
          token,
        ),
        staffFetch<{ jobs: NotificationJob[] }>(
          apiBase,
          `/api/portal/admin/cases/${caseId}/notification-jobs`,
          token,
        ),
        staffFetch<{ campaigns: SurveyCampaign[] }>(
          apiBase,
          `/api/portal/admin/cases/${caseId}/survey-campaigns`,
          token,
        ),
      ]);
      setFeedback(fb.feedback);
      setJobs(nj.jobs ?? []);
      setCampaigns(sc.campaigns ?? []);
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "Не удалось загрузить касания PDF.");
    } finally {
      setLoading(false);
    }
  }, [apiBase, caseId, onNotice, token]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function approveJob(jobId: string, channel: string) {
    try {
      const body =
        channel === "email" && clientEmail
          ? { to: clientEmail, mark_max_sent: false }
          : { mark_max_sent: channel === "max" };
      const out = await staffFetch<{ ok?: boolean; body?: string }>(
        apiBase,
        `/api/portal/admin/cases/${caseId}/notification-jobs/${jobId}/approve`,
        token,
        { method: "POST", body: JSON.stringify(body) },
      );
      if (out.body && channel === "max") {
        try {
          await navigator.clipboard.writeText(out.body);
          onNotice("Черновик MAX скопирован в буфер — вставьте в чат.");
        } catch {
          onNotice("Уведомление подтверждено. Текст в ответе API.");
        }
      } else {
        onNotice(channel === "email" ? "E-mail поставлен в очередь отправки." : "Уведомление подтверждено.");
      }
      await reload();
      onRefresh();
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "Не удалось подтвердить job.");
    }
  }

  async function cancelJob(jobId: string) {
    try {
      await staffFetch(
        apiBase,
        `/api/portal/admin/cases/${caseId}/notification-jobs/${jobId}/cancel`,
        token,
        { method: "POST", body: "{}" },
      );
      onNotice("Черновик уведомления отменён.");
      await reload();
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "Не удалось отменить job.");
    }
  }

  async function approveSurvey(campaignId: string) {
    try {
      const out = await staffFetch<ApproveSurveyResult>(
        apiBase,
        `/api/portal/admin/cases/${caseId}/survey-campaigns/${campaignId}/approve`,
        token,
        { method: "POST", body: JSON.stringify({ mark_sent: true, do_not_contact: false }) },
      );
      if (out.cancelled) {
        onNotice(`Опрос отменён: ${out.reason ?? "ограничение"}.`);
        await reload();
        return;
      }
      setSurveyDraft(out);
      if (out.body) {
        try {
          await navigator.clipboard.writeText(out.body);
        } catch {
          // ignore
        }
      }
      onNotice("Опрос подтверждён — текст в буфере, кнопки ниже.");
      await reload();
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "Не удалось подтвердить опрос.");
    }
  }

  async function cancelSurvey(campaignId: string) {
    try {
      await staffFetch(
        apiBase,
        `/api/portal/admin/cases/${caseId}/survey-campaigns/${campaignId}/cancel`,
        token,
        { method: "POST", body: "{}" },
      );
      onNotice("Опрос отменён.");
      await reload();
    } catch (error) {
      onNotice(error instanceof Error ? error.message : "Не удалось отменить опрос.");
    }
  }

  const pendingJobs = jobs.filter((j) => j.status === "draft");
  const pendingSurveys = campaigns.filter((c) =>
    ["draft", "scheduled", "approved"].includes(c.status),
  );

  if (loading && !feedback && jobs.length === 0) {
    return <p className="hint">Загрузка касаний после PDF…</p>;
  }

  return (
    <div className="diagnosis-delivery-panel">
      <h3 className="case-subhead">Обратная связь после PDF</h3>
      <p className="hint">
        Сервисные касания — только черновики до подтверждения. Отзыв в Яндекс — отдельно, после
        положительной оценки.
      </p>

      {feedback ? (
        <ul className="plain-list diagnosis-feedback-summary">
          <li>
            PDF выдан: <strong>{fmtDate(feedback.pdf_issued_at)}</strong>
            {feedback.pdf_opened_at ? (
              <span className="hint"> · открыт {fmtDate(feedback.pdf_opened_at)}</span>
            ) : null}
          </li>
          <li>
            Статус: <strong>{feedback.feedback_status ?? "none"}</strong>
            {feedback.clarity_score != null ? (
              <span className="hint"> · понятность {feedback.clarity_score}</span>
            ) : null}
            {feedback.first_plan_step_status ? (
              <span className="hint"> · первый шаг: {feedback.first_plan_step_status}</span>
            ) : null}
          </li>
          <li className="hint">
            Касание 2–3 дн.: {fmtDate(feedback.touch2_due_at)}
            {feedback.touch2_sent_at ? ` (отпр. ${fmtDate(feedback.touch2_sent_at)})` : ""}
            {" · "}
            10–14 дн.: {fmtDate(feedback.touch3_due_at)}
            {feedback.touch3_sent_at ? ` (отпр. ${fmtDate(feedback.touch3_sent_at)})` : ""}
          </li>
        </ul>
      ) : (
        <p className="hint">Запись feedback появится после публикации PDF.</p>
      )}

      {pendingJobs.length > 0 ? (
        <>
          <h4 className="case-subhead">Черновики уведомлений</h4>
          <ul className="plain-list">
            {pendingJobs.map((job) => (
              <li key={job.id} className="delivery-row">
                <span>
                  <strong>{job.job_type}</strong> · {job.channel} ·{" "}
                  {STATUS_LABELS[job.status] ?? job.status}
                </span>
                <div className="row-actions">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void approveJob(job.id, job.channel)}
                  >
                    {job.channel === "email" ? "Отправить e-mail" : "Подтвердить MAX"}
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    disabled={busy}
                    onClick={() => void cancelJob(job.id)}
                  >
                    Отмена
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      ) : jobs.length > 0 ? (
        <p className="hint">Активных черновиков уведомлений нет ({jobs.length} в истории).</p>
      ) : null}

      {pendingSurveys.length > 0 ? (
        <>
          <h4 className="case-subhead">Сервисные опросы</h4>
          <ul className="plain-list">
            {pendingSurveys.map((camp) => (
              <li key={camp.id} className="delivery-row">
                <span>
                  <strong>{SURVEY_LABELS[camp.survey_type] ?? camp.survey_type}</strong> ·{" "}
                  {camp.channel} · {STATUS_LABELS[camp.status] ?? camp.status}
                  {camp.scheduled_at ? (
                    <span className="hint"> · {fmtDate(camp.scheduled_at)}</span>
                  ) : null}
                </span>
                <div className="row-actions">
                  {(camp.status === "draft" || camp.status === "scheduled") && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void approveSurvey(camp.id)}
                    >
                      Подтвердить → {camp.channel === "email" ? "ссылки" : "MAX"}
                    </button>
                  )}
                  <button
                    type="button"
                    className="ghost"
                    disabled={busy}
                    onClick={() => void cancelSurvey(camp.id)}
                  >
                    Отмена
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      ) : campaigns.some((c) => c.status === "sent" || c.status === "completed") ? (
        <p className="hint">Открытых опросов нет — есть завершённые в истории.</p>
      ) : null}

      {surveyDraft?.body ? (
        <div className="survey-draft-preview">
          <h4 className="case-subhead">Текст опроса (скопирован)</h4>
          <pre className="draft">{surveyDraft.body}</pre>
          {surveyDraft.email_links && surveyDraft.email_links.length > 0 ? (
            <ul className="plain-list">
              {surveyDraft.email_links.map((link) => (
                <li key={link.answer_code}>
                  {link.label}:{" "}
                  <a href={link.url} target="_blank" rel="noreferrer">
                    ссылка подтверждения
                  </a>
                </li>
              ))}
            </ul>
          ) : null}
          {surveyDraft.attachments?.[0]?.payload?.buttons ? (
            <p className="hint">
              Кнопки MAX: отправьте текст выше в чат — клавиатура подставится ботом при
              approve из API (attachments в ответе).
            </p>
          ) : null}
          <button type="button" className="ghost" onClick={() => setSurveyDraft(null)}>
            Скрыть
          </button>
        </div>
      ) : null}
    </div>
  );
}
