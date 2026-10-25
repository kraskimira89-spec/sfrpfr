/** Адаптер: FunnelFacts → FunnelView (13 ступеней). Ничего не пишет в БД. */

import {
  FUNNEL_STAGE_IDS,
  STAGE_TITLES,
  type FunnelStageId,
  type FunnelStageState,
  type FunnelView,
  type StageAction,
  type StageActionId,
  type StageStatus,
  type StageView,
} from "./case-funnel-types";

export type {
  FunnelAction,
  FunnelStageId,
  FunnelStageState,
  FunnelView,
  LaterStageFacts,
  Loaded,
  StageAction,
  StageActionId,
  StageStatus,
  StageView,
} from "./case-funnel-types";

export {
  FUNNEL_STAGE_IDS,
  FUNNEL_STAGE_ORDER,
  LEGACY_TO_NEW,
  STAGE_IDS,
  STAGE_TITLES,
  defaultLaterStageFactsUnavailable,
  loaded,
  unavailable,
} from "./case-funnel-types";

export type OrderFacts = {
  state: "unknown" | "not_ordered" | "pending" | "paid" | "canceled" | "refunded";
  amountRub?: number;
  entitlement: "unknown" | "none" | "granted";
};

export type DeliverableFacts = {
  state: "unknown" | "not_started" | "working" | "ready" | "delivered";
};

export type FunnelFacts = {
  contacts: {
    known: boolean;
    reachable: boolean;
    requiredConsents: "unknown" | "missing" | "confirmed";
  };
  documents: {
    known: boolean;
    count: number;
    processing: boolean;
    sufficient: boolean;
    needsAttention: boolean;
  };
  precheck: {
    state: "unknown" | "not_started" | "queued" | "running" | "failed" | "completed";
    stale: boolean;
    outcome:
      | "unknown"
      | "discrepancies"
      | "clear"
      | "need_documents"
      | "need_clarification"
      | "staff_review";
    summaryDelivery: "unknown" | "not_sent" | "confirmed";
  };
  analysis: {
    recommendation: "unknown" | "not_needed" | "clarify" | "recommended";
    order: OrderFacts;
    result: DeliverableFacts;
  };
  appeals: {
    need: "unknown" | "not_needed" | "recommended";
    consent: "unknown" | "not_requested" | "pending" | "accepted" | "declined";
    order: OrderFacts;
    package: DeliverableFacts & {
      fileCount: number;
      allReviewed: boolean;
      clientApproved: boolean;
      /** Один draft без реестра файлов */
      registryMissing?: boolean;
    };
  };
  submission: {
    state: "unknown" | "not_started" | "awaiting_client" | "help_requested" | "confirmed";
  };
  followUp: {
    state: "unknown" | "inactive" | "active" | "paused" | "completed";
    callDue: boolean;
    nextCheckAt?: string;
  };
  response: {
    state: "unknown" | "none" | "received" | "reviewing" | "reviewed";
  };
  escalation: {
    decision: "unknown" | "not_needed" | "recommended";
    consent: "unknown" | "not_requested" | "pending" | "accepted" | "declined";
    order: OrderFacts;
    result: DeliverableFacts;
  };
  closure: {
    state: "unknown" | "open" | "review_required" | "closed";
    reason?: string;
    chronologyReady: boolean;
  };
  /** Причины unavailable по ступеням (не подменять not_started). */
  sourceNotes: Partial<Record<FunnelStageId, string>>;
  permissions: {
    allowedActions: readonly StageActionId[];
  };
};

const ACTION_LABELS: Record<StageActionId, string> = {
  edit_contacts: "Уточнить контакт",
  request_consents: "Запросить согласие",
  upload_documents: "Документы",
  run_precheck: "Проверить документы",
  view_precheck: "Открыть результат проверки",
  send_summary: "Отправить резюме",
  open_analysis_order: "Открыть заказ анализа",
  prepare_analysis: "Готовить анализ",
  deliver_analysis: "Передать анализ",
  request_appeals_consent: "Согласовать обращения",
  open_appeals_order: "Открыть заказ обращений",
  prepare_appeals: "Готовить обращения",
  deliver_appeals: "Передать обращения",
  record_submission: "Зафиксировать подачу",
  request_submission_help: "Нужен звонок",
  schedule_call: "План звонка",
  record_follow_up: "Записать контроль",
  review_response: "Разобрать ответ",
  open_escalation: "Доп. пакет",
  review_closure: "Проверить завершение",
  view_history: "История",
};

function act(
  id: StageActionId,
  enabled = true,
  disabledReason?: string,
): StageAction {
  return {
    id,
    label: ACTION_LABELS[id],
    enabled,
    disabledReason,
  };
}

function stage(
  id: FunnelStageId,
  status: StageStatus,
  summary: string,
  options: {
    blockers?: readonly string[];
    actions?: readonly StageAction[];
    dueAt?: string;
    title?: string;
  } = {},
): StageView {
  return {
    id,
    title: options.title ?? STAGE_TITLES[id],
    status,
    summary,
    blockers: options.blockers ?? [],
    actions: options.actions ?? [],
    dueAt: options.dueAt,
  };
}

function unknownStage(id: FunnelStageId, summary = "Статус не удалось определить"): StageView {
  return stage(id, "unknown", summary);
}

export function paymentTitle(label: string, order: OrderFacts): string {
  const amount = order.amountRub;
  if (typeof amount !== "number" || !Number.isFinite(amount) || amount <= 0) {
    return label;
  }
  return `${label} · ${new Intl.NumberFormat("ru-RU").format(amount)} ₽`;
}

function paymentStage(
  id: FunnelStageId,
  label: string,
  order: OrderFacts,
  prerequisite: "ready" | "blocked" | "not_required" | "unknown",
  actionId: StageActionId,
  sourceNote?: string,
): StageView {
  if (sourceNote) {
    return unknownStage(id, sourceNote);
  }
  const title = paymentTitle(label, order);
  if (order.state === "paid") {
    return stage(id, "done", "Оплата подтверждена", {
      title,
      actions: [act(actionId)],
    });
  }
  if (order.state === "refunded") {
    return stage(id, "needs_action", "Возврат подтверждён", {
      title,
      actions: [act(actionId)],
    });
  }
  if (order.state === "pending") {
    return stage(id, "waiting", "Заказ ожидает оплаты", {
      title,
      actions: [act(actionId)],
    });
  }
  if (order.state === "canceled") {
    return stage(id, "needs_action", "Заказ отменён", {
      title,
      actions: [act(actionId)],
    });
  }
  if (order.state === "unknown") {
    return unknownStage(id, "Статус заказа или оплаты недоступен");
  }
  if (prerequisite === "not_required") {
    return stage(id, "not_required", "Услуга сейчас не требуется", { title });
  }
  if (prerequisite === "unknown") {
    return unknownStage(id, "Сначала нужно определить следующий шаг");
  }
  if (prerequisite === "blocked") {
    return stage(id, "blocked", "Оформление пока недоступно", {
      title,
      blockers: ["Не выполнены условия предыдущего этапа"],
    });
  }
  return stage(id, "not_started", "Условия услуги можно согласовать", {
    title,
    actions: [act(actionId)],
  });
}

function deliverableStage(
  id: FunnelStageId,
  title: string,
  result: DeliverableFacts,
  entitlement: OrderFacts["entitlement"],
  prepareAction: StageActionId,
  deliverAction: StageActionId,
  sourceNote?: string,
): StageView {
  if (sourceNote) return unknownStage(id, sourceNote);
  if (result.state === "delivered") {
    return stage(id, "done", "Передача результата подтверждена", {
      title,
      actions: [act("view_history")],
    });
  }
  if (result.state === "unknown") {
    return unknownStage(id, "Состояние результата недоступно");
  }
  if (entitlement !== "granted") {
    return stage(
      id,
      entitlement === "unknown" ? "unknown" : "blocked",
      "Право на работу и выдачу услуги не подтверждено",
      {
        title,
        blockers: ["Проверить заказ и подтверждённое право на услугу"],
      },
    );
  }
  if (result.state === "working") {
    return stage(id, "in_progress", "Результат готовится", {
      title,
      actions: [act(prepareAction)],
    });
  }
  if (result.state === "ready") {
    return stage(id, "needs_action", "Результат готов к передаче", {
      title,
      actions: [act(deliverAction)],
    });
  }
  return stage(id, "not_started", "Можно начать работу", {
    title,
    actions: [act(prepareAction)],
  });
}

export function buildFunnelStages(f: FunnelFacts): StageView[] {
  const notes = f.sourceNotes;
  const stages: StageView[] = [];

  if (!f.contacts.known || f.contacts.requiredConsents === "unknown") {
    stages.push(unknownStage("contact_consents"));
  } else if (!f.contacts.reachable) {
    stages.push(
      stage("contact_consents", "needs_action", "Нужно подтвердить контакт для связи", {
        actions: [act("edit_contacts")],
      }),
    );
  } else if (f.contacts.requiredConsents === "missing") {
    stages.push(
      stage("contact_consents", "needs_action", "Не получены необходимые согласия", {
        actions: [act("request_consents")],
      }),
    );
  } else {
    stages.push(
      stage("contact_consents", "done", "Контакт и необходимые согласия подтверждены"),
    );
  }

  if (!f.documents.known) {
    stages.push(unknownStage("documents"));
  } else if (f.documents.count === 0) {
    stages.push(
      stage("documents", "not_started", "Документы не получены", {
        actions: [act("upload_documents")],
      }),
    );
  } else if (f.documents.processing) {
    stages.push(
      stage("documents", "in_progress", `Получено: ${f.documents.count}. Идёт обработка`),
    );
  } else if (!f.documents.sufficient || f.documents.needsAttention) {
    stages.push(
      stage("documents", "needs_action", "Нужно уточнить комплект или качество документов", {
        actions: [act("upload_documents"), act("run_precheck")],
      }),
    );
  } else {
    stages.push(
      stage(
        "documents",
        "done",
        `Комплект для текущей проверки подготовлен: ${f.documents.count}`,
      ),
    );
  }

  const p = f.precheck;
  if (p.state === "unknown") {
    stages.push(unknownStage("precheck_summary"));
  } else if (p.state === "queued" || p.state === "running") {
    stages.push(
      stage(
        "precheck_summary",
        p.state === "queued" ? "waiting" : "in_progress",
        p.state === "queued" ? "Проверка в очереди" : "Идёт проверка",
      ),
    );
  } else if (p.stale) {
    stages.push(
      stage(
        "precheck_summary",
        "needs_action",
        "Документы изменились — прежний результат устарел",
        { actions: [act("run_precheck")] },
      ),
    );
  } else if (p.state === "failed") {
    stages.push(
      stage("precheck_summary", "needs_action", "Проверка не завершена", {
        actions: [act("run_precheck")],
      }),
    );
  } else if (p.state === "not_started") {
    stages.push(
      stage(
        "precheck_summary",
        f.documents.sufficient ? "not_started" : "blocked",
        "Проверка ещё не выполнена",
        {
          actions: f.documents.sufficient ? [act("run_precheck")] : [],
          blockers: f.documents.sufficient ? [] : ["Нужен пригодный комплект документов"],
        },
      ),
    );
  } else {
    const needsClarification = ["need_documents", "need_clarification", "staff_review"].includes(
      p.outcome,
    );
    stages.push(
      stage(
        "precheck_summary",
        p.outcome === "unknown"
          ? "unknown"
          : needsClarification || p.summaryDelivery !== "confirmed"
            ? "needs_action"
            : "done",
        p.outcome === "clear"
          ? "В проверенном объёме расхождений не найдено"
          : p.outcome === "discrepancies"
            ? "Есть расхождения между источниками"
            : "Требуется уточнение результата",
        {
          actions: [
            !needsClarification && p.outcome !== "unknown" && p.summaryDelivery === "not_sent"
              ? act("send_summary")
              : act("view_precheck"),
          ],
        },
      ),
    );
  }

  stages.push(
    paymentStage(
      "analysis_payment",
      STAGE_TITLES.analysis_payment,
      f.analysis.order,
      p.stale
        ? "blocked"
        : f.analysis.recommendation === "recommended"
          ? "ready"
          : f.analysis.recommendation === "not_needed"
            ? "not_required"
            : f.analysis.recommendation === "unknown"
              ? "unknown"
              : "blocked",
      "open_analysis_order",
      notes.analysis_payment,
    ),
  );

  stages.push(
    deliverableStage(
      "full_analysis",
      STAGE_TITLES.full_analysis,
      f.analysis.result,
      f.analysis.order.entitlement,
      "prepare_analysis",
      "deliver_analysis",
      notes.full_analysis,
    ),
  );

  const a = f.appeals;
  if (a.need === "not_needed" || a.consent === "declined") {
    stages.push(
      stage(
        "appeals_consent",
        "not_required",
        a.consent === "declined"
          ? "Клиент отказался от этого этапа"
          : "Подготовка обращений не требуется",
      ),
    );
  } else if (a.consent === "accepted") {
    stages.push(stage("appeals_consent", "done", "Состав работ согласован"));
  } else if (a.need === "unknown" || a.consent === "unknown") {
    stages.push(
      notes.appeals_consent
        ? unknownStage("appeals_consent", notes.appeals_consent)
        : unknownStage("appeals_consent"),
    );
  } else if (f.analysis.result.state !== "delivered") {
    stages.push(
      stage(
        "appeals_consent",
        "blocked",
        "Сначала нужно выдать и обсудить подробный анализ",
      ),
    );
  } else {
    stages.push(
      stage(
        "appeals_consent",
        a.consent === "pending" ? "waiting" : "needs_action",
        "Нужно согласовать план и объём подготовки",
        { actions: [act("request_appeals_consent")] },
      ),
    );
  }

  // 7 — оплата обращений (не завершает подготовку)
  stages.push(
    paymentStage(
      "appeals_payment",
      STAGE_TITLES.appeals_payment,
      a.order,
      a.need === "not_needed" || a.consent === "declined"
        ? "not_required"
        : a.consent === "accepted"
          ? "ready"
          : a.consent === "unknown"
            ? "unknown"
            : "blocked",
      "open_appeals_order",
      notes.appeals_payment,
    ),
  );

  // 8 — обращения
  if (notes.appeals_documents) {
    stages.push(unknownStage("appeals_documents", notes.appeals_documents));
  } else {
    const appealsView = deliverableStage(
      "appeals_documents",
      STAGE_TITLES.appeals_documents,
      a.package,
      a.order.entitlement,
      "prepare_appeals",
      "deliver_appeals",
    );
    if (a.package.registryMissing && a.package.state !== "delivered") {
      stages.push(
        stage(
          "appeals_documents",
          a.package.state === "working" ? "in_progress" : appealsView.status,
          "Есть черновик проекта; реестра отдельных файлов обращений в API нет",
          {
            actions: appealsView.actions,
            blockers: ["Нет реестра отдельных исходящих документов"],
          },
        ),
      );
    } else if (
      a.package.state === "ready" &&
      a.order.entitlement === "granted" &&
      (a.package.fileCount === 0 || !a.package.allReviewed || !a.package.clientApproved)
    ) {
      stages.push(
        stage("appeals_documents", "needs_action", "Пакет требует проверки или согласования", {
          actions: [act("prepare_appeals")],
          blockers: [
            ...(a.package.fileCount === 0 ? ["Нет файлов обращений"] : []),
            ...(!a.package.allReviewed ? ["Не все документы проверены"] : []),
            ...(!a.package.clientApproved ? ["Нет согласования клиента"] : []),
          ],
        }),
      );
    } else {
      stages.push(appealsView);
    }
  }

  // 9 — подача
  if (notes.submission) {
    stages.push(unknownStage("submission", notes.submission));
  } else {
    const submission = f.submission.state;
    stages.push(
      submission === "unknown"
        ? unknownStage("submission")
        : submission === "confirmed"
          ? stage("submission", "done", "Подача подтверждена", {
              actions: [act("view_history")],
            })
          : submission === "help_requested"
            ? stage("submission", "needs_action", "Клиенту нужен звонок", {
                actions: [act("schedule_call"), act("request_submission_help")],
              })
            : a.package.state !== "delivered"
              ? stage(
                  "submission",
                  "blocked",
                  "Сначала нужно передать согласованный пакет",
                )
              : stage("submission", "waiting", "Ожидаем сведения о подаче", {
                  actions: [act("record_submission"), act("request_submission_help")],
                }),
    );
  }

  // 10 — контроль
  if (notes.follow_up) {
    stages.push(unknownStage("follow_up", notes.follow_up));
  } else {
    const follow = f.followUp;
    const submission = f.submission.state;
    stages.push(
      follow.state === "unknown"
        ? unknownStage("follow_up")
        : follow.state === "completed"
          ? stage("follow_up", "done", "Этот цикл контроля завершён")
          : submission !== "confirmed"
            ? stage("follow_up", "blocked", "Нет подтверждённой даты подачи")
            : stage(
                "follow_up",
                follow.callDue
                  ? "needs_action"
                  : follow.state === "active"
                    ? "in_progress"
                    : "waiting",
                follow.callDue
                  ? "Нужно уточнить состояние дела звонком"
                  : follow.state === "paused"
                    ? "Контроль приостановлен"
                    : follow.state === "inactive"
                      ? "Нужно определить порядок контроля"
                      : "Ожидаем обновление",
                {
                  actions: [act(follow.callDue ? "schedule_call" : "record_follow_up")],
                  dueAt: follow.nextCheckAt,
                },
              ),
    );
  }

  // 11 — ответ
  if (notes.response_review) {
    stages.push(unknownStage("response_review", notes.response_review));
  } else {
    const response = f.response.state;
    stages.push(
      response === "unknown"
        ? unknownStage("response_review")
        : stage(
            "response_review",
            response === "reviewed"
              ? "done"
              : response === "reviewing"
                ? "in_progress"
                : response === "received"
                  ? "needs_action"
                  : "waiting",
            response === "reviewed"
              ? "Ответ разобран, следующий шаг определён"
              : response === "reviewing"
                ? "Идёт разбор ответа"
                : response === "received"
                  ? "Получен документ — нужен разбор"
                  : "Ответ пока не зарегистрирован",
            {
              actions:
                response === "received" || response === "reviewing"
                  ? [act("review_response")]
                  : [],
            },
          ),
    );
  }

  // 12 — доп. пакет
  if (notes.escalation_package) {
    stages.push(unknownStage("escalation_package", notes.escalation_package));
  } else {
    const e = f.escalation;
    if (e.result.state === "delivered") {
      stages.push(
        stage("escalation_package", "done", "Передача дополнительного пакета подтверждена", {
          actions: [act("view_history")],
        }),
      );
    } else if (e.decision === "not_needed" || e.consent === "declined") {
      stages.push(
        stage(
          "escalation_package",
          "not_required",
          e.consent === "declined"
            ? "Клиент не заказал дополнительную работу"
            : "Дополнительный пакет не требуется",
        ),
      );
    } else if (e.decision === "unknown") {
      stages.push(
        unknownStage(
          "escalation_package",
          "Необходимость следующего пакета ещё не определена",
        ),
      );
    } else if (e.consent !== "accepted") {
      stages.push(
        stage(
          "escalation_package",
          e.consent === "unknown" ? "unknown" : "needs_action",
          "Нужно согласовать основания и состав работ",
          { actions: [act("open_escalation")] },
        ),
      );
    } else if (e.order.entitlement !== "granted") {
      const payment = paymentStage(
        "escalation_package",
        STAGE_TITLES.escalation_package,
        e.order,
        "ready",
        "open_escalation",
      );
      if (payment.status === "done") {
        stages.push(
          stage("escalation_package", "needs_action", "Оплата есть, право на работу нужно сверить", {
            title: payment.title,
            actions: [act("open_escalation")],
          }),
        );
      } else {
        stages.push(payment);
      }
    } else {
      stages.push(
        deliverableStage(
          "escalation_package",
          paymentTitle(STAGE_TITLES.escalation_package, e.order),
          e.result,
          e.order.entitlement,
          "open_escalation",
          "open_escalation",
        ),
      );
    }
  }

  // 13 — итог
  if (notes.closure) {
    stages.push(unknownStage("closure", notes.closure));
  } else {
    stages.push(
      f.closure.state === "unknown"
        ? unknownStage("closure")
        : stage(
            "closure",
            f.closure.state === "closed"
              ? "done"
              : f.closure.state === "review_required"
                ? "needs_action"
                : "not_started",
            f.closure.state === "closed"
              ? f.closure.reason || "Завершение дела подтверждено"
              : f.closure.chronologyReady
                ? "Хронология подготовлена; дело остаётся открытым"
                : "Дело открыто",
            {
              actions: [
                act(f.closure.state === "review_required" ? "review_closure" : "view_history"),
              ],
            },
          ),
    );
  }

  const allowed = new Set(f.permissions.allowedActions);
  return stages.map((item) => ({
    ...item,
    actions: item.actions.map((a) =>
      allowed.has(a.id)
        ? a
        : { ...a, enabled: false, disabledReason: a.disabledReason || "Недостаточно прав" },
    ),
  }));
}

export function selectCurrentStage(
  stages: readonly StageView[],
  explicitStage?: FunnelStageId,
  opts?: { closed?: boolean },
): FunnelStageId | null {
  if (opts?.closed) return "closure";
  if (explicitStage && stages.some((s) => s.id === explicitStage)) {
    return explicitStage;
  }
  const actionable = stages.find(
    (s) => s.status === "needs_action" && s.actions.some((a) => a.enabled),
  );
  if (actionable) return actionable.id;
  const active = stages.find((s) => s.status === "in_progress");
  if (active) return active.id;
  const waiting = stages.find((s) => s.status === "waiting");
  if (waiting) return waiting.id;
  return (
    stages.find((s) => s.status === "not_started" && s.actions.some((a) => a.enabled))?.id ?? null
  );
}

export function buildFunnelView(
  f: FunnelFacts,
  opts?: { explicitStage?: FunnelStageId; closed?: boolean },
): FunnelView {
  const stages = buildFunnelStages(f);
  return {
    stages,
    currentStageId: selectCurrentStage(stages, opts?.explicitStage, {
      closed: opts?.closed ?? f.closure.state === "closed",
    }),
  };
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
  id: FunnelStageId;
  label: string;
  state: FunnelStageState;
  reason: string;
  canAct: boolean;
  shortSummary: string;
  status: StageStatus;
  actions: readonly StageAction[];
  blockers: readonly string[];
};

export function viewsToFunnelStages(
  views: readonly StageView[],
  current: FunnelStageId | null,
  overdue: boolean,
): FunnelStage[] {
  return views.map((v) => ({
    id: v.id,
    label: v.title,
    state: stageStatusToShell(v.status, {
      overdue: overdue && v.id === current,
      isCurrent: v.id === current,
    }),
    reason: v.blockers[0] || v.summary,
    canAct: v.actions.some((a) => a.enabled),
    shortSummary: v.summary,
    status: v.status,
    actions: v.actions,
    blockers: v.blockers,
  }));
}

export function primaryCtaLabel(current: FunnelStageId, docsReady: boolean): string {
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

export const PLAN_READY_CHAT =
  "Подготовили материалы по вашему делу. Мы готовим документы и план — подаёте через СФР или Госуслуги вы сами. Решение принимает СФР. Если удобно — ответьте в этот чат.";

export const SERVICE_DESCRIPTION_CHAT =
  "Кратко об услуге: разбираем документы о стаже, готовим понятное резюме и при согласии — проекты обращений. Подачу через СФР/Госуслуги выполняете вы; решение принимает СФР.";

/** Полный Record панелей — TypeScript потребует новый ID. */
export type LaterPanelId = Extract<
  FunnelStageId,
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
