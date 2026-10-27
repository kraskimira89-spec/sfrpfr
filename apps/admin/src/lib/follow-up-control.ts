/** Ступень 10: UI-состояния внутренней контрольной даты (Asia/Yekaterinburg). */

export type FollowUpUiState =
  | "blocked"
  | "need_assign"
  | "awaiting_date"
  | "due_today"
  | "overdue_internal"
  | "done";

const CONTROL_TZ = "Asia/Yekaterinburg";

export const FOLLOW_UP_UI_LABELS: Record<FollowUpUiState, string> = {
  blocked: "Сначала зафиксируйте подачу (ступень 9)",
  need_assign: "Нужно назначить контроль",
  awaiting_date: "Ожидаем контрольной даты",
  due_today: "Сегодня проверить состояние",
  overdue_internal: "Просрочена внутренняя контрольная дата",
  done: "Ответ передан на разбор",
};

export function calendarDateInControlTz(
  iso: string | null | undefined,
  now: Date = new Date(),
): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: CONTROL_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(d);
}

export function todayInControlTz(now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: CONTROL_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}

export function deriveFollowUpUiState(opts: {
  submissionConfirmed: boolean;
  followUpCompleted: boolean;
  responseReceived: boolean;
  controlAt: string | null | undefined;
  now?: Date;
}): FollowUpUiState {
  if (opts.followUpCompleted || opts.responseReceived) return "done";
  if (!opts.submissionConfirmed) return "blocked";
  const day = calendarDateInControlTz(opts.controlAt, opts.now);
  if (!day) return "need_assign";
  const today = todayInControlTz(opts.now);
  if (day > today) return "awaiting_date";
  if (day === today) return "due_today";
  return "overdue_internal";
}
