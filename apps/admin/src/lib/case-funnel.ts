/** Реэкспорт адаптера + UI-хелперы для CaseFunnelMain. */

import { buildFunnel } from "./case-funnel-adapter";
import type {
  ActionId,
  FunnelFacts,
  FunnelStageState,
  FunnelView,
  StageId,
  StageStatus,
  StageView,
} from "./case-funnel-types";

export type {
  ActionId,
  Decision,
  FunnelFacts,
  FunnelStageId,
  FunnelStageState,
  FunnelView,
  Need,
  OrderFacts,
  StageId,
  StageStatus,
  StageView,
  WorkFacts,
} from "./case-funnel-types";

export {
  FUNNEL_STAGE_IDS,
  FUNNEL_STAGE_ORDER,
  LEGACY_TO_NEW,
  STAGE_IDS,
  STAGE_TITLES,
} from "./case-funnel-types";

export { buildFunnel, executeStageAction, type ActionHandlers } from "./case-funnel-adapter";

/** @deprecated используйте ActionId */
export type StageActionId = ActionId;
/** @deprecated используйте ActionId */
export type FunnelAction = ActionId;

export type StageAction = Readonly<{
  id: ActionId;
  label: string;
  enabled: boolean;
  disabledReason?: string;
}>;

const ACTION_LABELS: Record<ActionId, string> = {
  edit_contacts: "Уточнить контакт",
  upload_documents: "Документы",
  run_precheck: "Проверить документы",
  view_precheck: "Открыть результат проверки",
  send_summary: "Отправить резюме",
  open_analysis_order: "Открыть заказ анализа",
  open_analysis: "Открыть анализ",
  request_appeals_consent: "Согласовать обращения",
  open_appeals_order: "Открыть заказ обращений",
  open_appeals: "Открыть обращения",
  record_submission: "Зафиксировать подачу",
  schedule_call: "План звонка",
  record_follow_up: "Записать контроль",
  review_response: "Разобрать ответ",
  open_escalation: "Доп. пакет",
  review_closure: "Проверить завершение",
};

export function actionLabel(id: ActionId): string {
  return ACTION_LABELS[id];
}

/** @deprecated используйте buildFunnel */
export function buildFunnelStages(f: FunnelFacts): StageView[] {
  return [...buildFunnel(f).stages];
}

/** @deprecated используйте buildFunnel */
export function buildFunnelView(f: FunnelFacts): FunnelView {
  return buildFunnel(f);
}

export function selectCurrentStage(
  stages: readonly StageView[],
  explicitStage?: StageId,
  opts?: { closed?: boolean },
): StageId | null {
  if (opts?.closed) return "closure";
  if (explicitStage && stages.some((s) => s.id === explicitStage)) {
    return explicitStage;
  }
  return (
    stages.find((s) => s.status === "needs_action" && s.action)?.id ??
    stages.find((s) => s.status === "in_progress")?.id ??
    stages.find((s) => s.status === "waiting")?.id ??
    stages.find((s) => s.status === "not_started" && s.action)?.id ??
    null
  );
}

export function stageStatusToShell(
  status: StageStatus,
  opts?: { overdue?: boolean; isCurrent?: boolean },
): FunnelStageState {
  if (
    opts?.overdue &&
    (status === "needs_action" || status === "waiting" || status === "in_progress")
  ) {
    return "overdue";
  }
  if (status === "done") return "done";
  if (status === "waiting") return "waiting";
  if (status === "blocked") return "blocked";
  if (status === "needs_action" || status === "in_progress") {
    return opts?.isCurrent === false ? "todo" : "current";
  }
  return "todo";
}

export type FunnelStage = {
  id: StageId;
  label: string;
  state: FunnelStageState;
  reason: string;
  canAct: boolean;
  shortSummary: string;
  status: StageStatus;
  action?: ActionId;
  actions: readonly StageAction[];
  blockers: readonly string[];
};

export function viewsToFunnelStages(
  views: readonly StageView[],
  current: StageId | null,
  overdue: boolean,
): FunnelStage[] {
  return views.map((v) => {
    const actions: StageAction[] = v.action
      ? [{ id: v.action, label: ACTION_LABELS[v.action], enabled: true }]
      : [];
    return {
      id: v.id,
      label: v.title,
      state: stageStatusToShell(v.status, {
        overdue: overdue && v.id === current,
        isCurrent: v.id === current,
      }),
      reason: v.blockers[0] || v.summary,
      canAct: Boolean(v.action),
      shortSummary: v.summary,
      status: v.status,
      action: v.action,
      actions,
      blockers: v.blockers,
    };
  });
}

export function primaryCtaLabel(current: StageId, docsReady: boolean): string {
  if (current === "contact_consents") return "Настроить канал связи";
  if (current === "documents") return docsReady ? "Запустить проверку" : "Запросить документы";
  if (current === "precheck_summary") return "Открыть результат проверки";
  if (current === "analysis_payment") return "Открыть оплату анализа";
  if (current === "full_analysis") return "Открыть подробный анализ";
  if (current === "appeals_consent") return "Согласовать обращения";
  if (current === "appeals_payment") return "Открыть оплату обращений";
  if (current === "appeals_documents") return "Открыть обращения";
  if (current === "submission") return "Зафиксировать подачу";
  if (current === "follow_up") return "Контроль рассмотрения";
  if (current === "response_review") return "Разобрать ответ СФР";
  if (current === "escalation_package") return "Дополнительный пакет";
  return "Итог дела";
}

export function slaHint(detail: {
  waiting_on?: string | null;
  next_action_at?: string | null;
}): string {
  const wait = detail.waiting_on || "";
  if (wait === "client") return "Ждём клиента";
  if (wait === "archive") return "Ждём архив";
  if (wait === "sfr") return "Ждём ответ СФР";
  if (wait === "payment") return "Ждём оплату";
  if (detail.next_action_at) {
    const due = new Date(detail.next_action_at);
    if (!Number.isNaN(due.getTime())) {
      const diffH = (due.getTime() - Date.now()) / 36e5;
      if (diffH < 0)
        return `Просрочено с ${due.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}`;
      if (diffH < 24)
        return `Срок сегодня ${due.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}`;
      return `Срок ${due.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}`;
    }
  }
  if (wait === "staff") return "Ответить в приоритете";
  return "Срок не задан";
}

export const DOC_REQUEST_ILS =
  "Здравствуйте! Для проверки нужна выписка ИЛС с Госуслуг. Можно прислать файл (PDF/JPG/PNG) прямо в этот чат — примем, специалист увидит. Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. Решение принимает СФР.";

export const DOC_REQUEST_LABOR =
  "Здравствуйте! Подготовьте трудовую книжку или сведения о стаже. Можно прислать сканы (PDF/JPG/PNG) прямо в этот чат — примем, специалист увидит. Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. Решение принимает СФР.";

export const DOC_REQUEST_SFR_RESPONSE =
  "Здравствуйте! Когда придёт ответ или решение СФР (отказ, уведомление, письмо), пришлите, пожалуйста, файл или скан прямо в этот чат — PDF, JPG или PNG. Специалист разберёт и подскажет следующие шаги. Подачу и дальнейшие обращения через СФР или Госуслуги выполняете вы сами. Решение принимает СФР.";

export const PLAN_READY_CHAT =
  "Подготовили подробный письменный разбор по вашим документам (сверка выписки ИЛС и трудовой / справок). Кратко: что нашли, на какие периоды обратить внимание и какие шаги дальше. Файл разбора можем прислать в этот чат или на e-mail — напишите, как удобнее. Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. Решение принимает СФР.";

/** Когда PDF уже загружен — короткое уведомление клиенту. */
export const ANALYSIS_PDF_READY_CHAT =
  "Подробный разбор по стажу готов: файл с итогами сверки можно получить в этом чате. Напишите, если нужны пояснения по пунктам. Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. Решение принимает СФР.";

export const SERVICE_DESCRIPTION_CHAT =
  "Кратко об услуге: разбираем документы о стаже, готовим понятное резюме и при согласии — проекты обращений. Подачу через СФР/Госуслуги выполняете вы; решение принимает СФР.";

/** Ссылка на форму отзыва (Яндекс /otzyv/). */
export const REVIEW_OTZYV_CHAT =
  "Здравствуйте! Если вам было удобно работать с нами, будем благодарны за короткий отзыв — это помогает другим людям найти сервис: https://proverkastaza.ru/otzyv/ Публикуете вы сами. Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. Решение принимает СФР.";

/** Анкета / короткое «интервью» для формулировки отзыва. */
export const REVIEW_INTERVIEW_CHAT =
  "Здравствуйте! Если удобно, можно пройти короткую анкету (как мини-интервью) — по ответам соберём черновик отзыва, публикуете вы сами: https://proverkastaza.ru/anketa-otzyv/ Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. Решение принимает СФР.";

export type LaterPanelId = Extract<
  StageId,
  | "appeals_payment"
  | "appeals_documents"
  | "submission"
  | "follow_up"
  | "response_review"
  | "escalation_package"
  | "closure"
>;

export const LATER_STAGE_IDS = [
  "appeals_payment",
  "appeals_documents",
  "submission",
  "follow_up",
  "response_review",
  "escalation_package",
  "closure",
] as const satisfies readonly LaterPanelId[];
