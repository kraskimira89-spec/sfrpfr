/** Адаптер воронки: 13 UI-ступеней из FunnelFacts. Ничего не пишет в БД. */

export const STAGE_IDS = [
  "contact_consents",
  "documents",
  "precheck_summary",
  "analysis_payment",
  "full_analysis",
  "appeals_consent",
  "appeals_payment",
  "appeals_documents",
  "submission",
  "follow_up",
  "response_review",
  "escalation_package",
  "closure",
] as const;

export type FunnelStageId = (typeof STAGE_IDS)[number];

/** @deprecated alias — то же, что STAGE_IDS */
export const FUNNEL_STAGE_ORDER = STAGE_IDS;

export type StageStatus =
  | "not_started"
  | "in_progress"
  | "waiting"
  | "needs_action"
  | "done"
  | "blocked"
  | "not_required"
  | "unknown";

/** Состояния для StageShell / StageMark (UI-оболочка). */
export type FunnelStageState =
  | "done"
  | "current"
  | "waiting"
  | "blocked"
  | "overdue"
  | "todo";

export type FunnelAction =
  | "edit_contacts"
  | "request_consents"
  | "upload_documents"
  | "run_precheck"
  | "view_precheck"
  | "send_summary"
  | "view_analysis_order"
  | "prepare_analysis"
  | "deliver_analysis"
  | "request_appeals_consent"
  | "view_appeals_order"
  | "prepare_appeals"
  | "deliver_appeals"
  | "record_submission"
  | "schedule_call"
  | "record_follow_up"
  | "review_response"
  | "open_escalation"
  | "review_closure"
  | "view_history";

export type StageView = {
  id: FunnelStageId;
  title: string;
  status: StageStatus;
  summary: string;
  blockers: string[];
  action?: FunnelAction;
  dueAt?: string;
};

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
  permissions: {
    allowedActions: readonly FunnelAction[];
  };
};

function stage(
  id: FunnelStageId,
  title: string,
  status: StageStatus,
  summary: string,
  options: { blockers?: string[]; action?: FunnelAction; dueAt?: string } = {},
): StageView {
  return {
    id,
    title,
    status,
    summary,
    blockers: options.blockers ?? [],
    action: options.action,
    dueAt: options.dueAt,
  };
}

function unknown(
  id: FunnelStageId,
  title: string,
  summary = "Статус не удалось определить",
): StageView {
  return stage(id, title, "unknown", summary);
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
  action: FunnelAction,
): StageView {
  const title = paymentTitle(label, order);

  if (order.state === "paid") {
    return stage(id, title, "done", "Оплата подтверждена", { action });
  }
  if (order.state === "refunded") {
    return stage(id, title, "needs_action", "Возврат подтверждён", { action });
  }
  if (order.state === "pending") {
    return stage(id, title, "waiting", "Заказ ожидает оплаты", { action });
  }
  if (order.state === "canceled") {
    return stage(id, title, "needs_action", "Заказ отменён", { action });
  }
  if (order.state === "unknown") {
    return unknown(id, title, "Статус заказа или оплаты недоступен");
  }
  if (prerequisite === "not_required") {
    return stage(id, title, "not_required", "Услуга сейчас не требуется");
  }
  if (prerequisite === "unknown") {
    return unknown(id, title, "Сначала нужно определить следующий шаг");
  }
  if (prerequisite === "blocked") {
    return stage(id, title, "blocked", "Оформление пока недоступно", {
      blockers: ["Не выполнены условия предыдущего этапа"],
    });
  }
  return stage(id, title, "not_started", "Условия услуги можно согласовать", { action });
}

function deliverableStage(
  id: FunnelStageId,
  title: string,
  result: DeliverableFacts,
  entitlement: OrderFacts["entitlement"],
  prepareAction: FunnelAction,
  deliverAction: FunnelAction,
): StageView {
  if (result.state === "delivered") {
    return stage(id, title, "done", "Передача результата подтверждена", {
      action: "view_history",
    });
  }
  if (result.state === "unknown") {
    return unknown(id, title, "Состояние результата недоступно");
  }
  if (entitlement !== "granted") {
    return stage(
      id,
      title,
      entitlement === "unknown" ? "unknown" : "blocked",
      "Право на работу и выдачу услуги не подтверждено",
      { blockers: ["Проверить заказ и подтверждённое право на услугу"] },
    );
  }
  if (result.state === "working") {
    return stage(id, title, "in_progress", "Результат готовится", { action: prepareAction });
  }
  if (result.state === "ready") {
    return stage(id, title, "needs_action", "Результат готов к передаче", {
      action: deliverAction,
    });
  }
  return stage(id, title, "not_started", "Можно начать работу", { action: prepareAction });
}

export function buildFunnelStages(f: FunnelFacts): StageView[] {
  const stages: StageView[] = [];

  if (!f.contacts.known || f.contacts.requiredConsents === "unknown") {
    stages.push(unknown("contact_consents", "Контакт и согласия"));
  } else if (!f.contacts.reachable) {
    stages.push(
      stage("contact_consents", "Контакт и согласия", "needs_action", "Нужно подтвердить контакт для связи", {
        action: "edit_contacts",
      }),
    );
  } else if (f.contacts.requiredConsents === "missing") {
    stages.push(
      stage("contact_consents", "Контакт и согласия", "needs_action", "Не получены необходимые согласия", {
        action: "request_consents",
      }),
    );
  } else {
    stages.push(
      stage("contact_consents", "Контакт и согласия", "done", "Контакт и необходимые согласия подтверждены"),
    );
  }

  if (!f.documents.known) {
    stages.push(unknown("documents", "Документы"));
  } else if (f.documents.count === 0) {
    stages.push(
      stage("documents", "Документы", "not_started", "Документы не получены", {
        action: "upload_documents",
      }),
    );
  } else if (f.documents.processing) {
    stages.push(
      stage(
        "documents",
        "Документы",
        "in_progress",
        `Получено: ${f.documents.count}. Идёт обработка`,
      ),
    );
  } else if (!f.documents.sufficient || f.documents.needsAttention) {
    stages.push(
      stage(
        "documents",
        "Документы",
        "needs_action",
        "Нужно уточнить комплект или качество документов",
        { action: "upload_documents" },
      ),
    );
  } else {
    stages.push(
      stage(
        "documents",
        "Документы",
        "done",
        `Комплект для текущей проверки подготовлен: ${f.documents.count}`,
      ),
    );
  }

  const p = f.precheck;
  if (p.state === "unknown") {
    stages.push(unknown("precheck_summary", "Первичная проверка и резюме"));
  } else if (p.state === "queued" || p.state === "running") {
    stages.push(
      stage(
        "precheck_summary",
        "Первичная проверка и резюме",
        p.state === "queued" ? "waiting" : "in_progress",
        p.state === "queued" ? "Проверка в очереди" : "Идёт проверка",
      ),
    );
  } else if (p.stale) {
    stages.push(
      stage(
        "precheck_summary",
        "Первичная проверка и резюме",
        "needs_action",
        "Документы изменились — прежний результат устарел",
        { action: "run_precheck" },
      ),
    );
  } else if (p.state === "failed") {
    stages.push(
      stage("precheck_summary", "Первичная проверка и резюме", "needs_action", "Проверка не завершена", {
        action: "run_precheck",
      }),
    );
  } else if (p.state === "not_started") {
    stages.push(
      stage(
        "precheck_summary",
        "Первичная проверка и резюме",
        f.documents.sufficient ? "not_started" : "blocked",
        "Проверка ещё не выполнена",
        {
          action: f.documents.sufficient ? "run_precheck" : undefined,
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
        "Первичная проверка и резюме",
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
          action:
            !needsClarification && p.outcome !== "unknown" && p.summaryDelivery === "not_sent"
              ? "send_summary"
              : "view_precheck",
        },
      ),
    );
  }

  stages.push(
    paymentStage(
      "analysis_payment",
      "Оплата подробного анализа",
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
      "view_analysis_order",
    ),
  );

  stages.push(
    deliverableStage(
      "full_analysis",
      "Подробный анализ",
      f.analysis.result,
      f.analysis.order.entitlement,
      "prepare_analysis",
      "deliver_analysis",
    ),
  );

  const a = f.appeals;
  if (a.need === "not_needed" || a.consent === "declined") {
    stages.push(
      stage(
        "appeals_consent",
        "Согласование обращений",
        "not_required",
        a.consent === "declined"
          ? "Клиент отказался от этого этапа"
          : "Подготовка обращений не требуется",
      ),
    );
  } else if (a.consent === "accepted") {
    stages.push(
      stage("appeals_consent", "Согласование обращений", "done", "Состав работ согласован"),
    );
  } else if (a.need === "unknown" || a.consent === "unknown") {
    stages.push(unknown("appeals_consent", "Согласование обращений"));
  } else if (f.analysis.result.state !== "delivered") {
    stages.push(
      stage(
        "appeals_consent",
        "Согласование обращений",
        "blocked",
        "Сначала нужно выдать и обсудить подробный анализ",
      ),
    );
  } else {
    stages.push(
      stage(
        "appeals_consent",
        "Согласование обращений",
        a.consent === "pending" ? "waiting" : "needs_action",
        "Нужно согласовать план и объём подготовки",
        { action: "request_appeals_consent" },
      ),
    );
  }

  stages.push(
    paymentStage(
      "appeals_payment",
      "Оплата подготовки обращений",
      a.order,
      a.need === "not_needed" || a.consent === "declined"
        ? "not_required"
        : a.consent === "accepted"
          ? "ready"
          : a.consent === "unknown"
            ? "unknown"
            : "blocked",
      "view_appeals_order",
    ),
  );

  const appealsView = deliverableStage(
    "appeals_documents",
    "Обращения и передача клиенту",
    a.package,
    a.order.entitlement,
    "prepare_appeals",
    "deliver_appeals",
  );
  if (
    a.package.state === "ready" &&
    a.order.entitlement === "granted" &&
    (a.package.fileCount === 0 || !a.package.allReviewed || !a.package.clientApproved)
  ) {
    appealsView.status = "needs_action";
    appealsView.summary = "Пакет требует проверки или согласования";
    appealsView.action = "prepare_appeals";
    appealsView.blockers = [
      ...(a.package.fileCount === 0 ? ["Нет файлов обращений"] : []),
      ...(!a.package.allReviewed ? ["Не все документы проверены"] : []),
      ...(!a.package.clientApproved ? ["Нет согласования клиента"] : []),
    ];
  }
  stages.push(appealsView);

  const submission = f.submission.state;
  stages.push(
    submission === "unknown"
      ? unknown("submission", "Подача и помощь специалиста")
      : submission === "confirmed"
        ? stage("submission", "Подача и помощь специалиста", "done", "Подача подтверждена", {
            action: "view_history",
          })
        : submission === "help_requested"
          ? stage(
              "submission",
              "Подача и помощь специалиста",
              "needs_action",
              "Клиенту нужен звонок",
              { action: "schedule_call" },
            )
          : a.package.state !== "delivered"
            ? stage(
                "submission",
                "Подача и помощь специалиста",
                "blocked",
                "Сначала нужно передать согласованный пакет",
              )
            : stage(
                "submission",
                "Подача и помощь специалиста",
                "waiting",
                "Ожидаем сведения о подаче",
                { action: "record_submission" },
              ),
  );

  const follow = f.followUp;
  stages.push(
    follow.state === "unknown"
      ? unknown("follow_up", "Контроль рассмотрения")
      : follow.state === "completed"
        ? stage("follow_up", "Контроль рассмотрения", "done", "Этот цикл контроля завершён")
        : submission !== "confirmed"
          ? stage(
              "follow_up",
              "Контроль рассмотрения",
              "blocked",
              "Нет подтверждённой даты подачи",
            )
          : stage(
              "follow_up",
              "Контроль рассмотрения",
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
                action: follow.callDue ? "schedule_call" : "record_follow_up",
                dueAt: follow.nextCheckAt,
              },
            ),
  );

  const response = f.response.state;
  stages.push(
    response === "unknown"
      ? unknown("response_review", "Ответ СФР и дальнейшие действия")
      : stage(
          "response_review",
          "Ответ СФР и дальнейшие действия",
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
            action:
              response === "received" || response === "reviewing" ? "review_response" : undefined,
          },
        ),
  );

  const e = f.escalation;
  if (e.result.state === "delivered") {
    stages.push(
      stage(
        "escalation_package",
        "Дополнительные обращения",
        "done",
        "Передача дополнительного пакета подтверждена",
        { action: "view_history" },
      ),
    );
  } else if (e.decision === "not_needed" || e.consent === "declined") {
    stages.push(
      stage(
        "escalation_package",
        "Дополнительные обращения",
        "not_required",
        e.consent === "declined"
          ? "Клиент не заказал дополнительную работу"
          : "Дополнительный пакет не требуется",
      ),
    );
  } else if (e.decision === "unknown") {
    stages.push(
      unknown(
        "escalation_package",
        "Дополнительные обращения",
        "Необходимость следующего пакета ещё не определена",
      ),
    );
  } else if (e.consent !== "accepted") {
    stages.push(
      stage(
        "escalation_package",
        "Дополнительные обращения",
        e.consent === "unknown" ? "unknown" : "needs_action",
        "Нужно согласовать основания и состав работ",
        { action: "open_escalation" },
      ),
    );
  } else if (e.order.entitlement !== "granted") {
    const payment = paymentStage(
      "escalation_package",
      "Дополнительные обращения",
      e.order,
      "ready",
      "open_escalation",
    );
    if (payment.status === "done") {
      payment.status = "needs_action";
      payment.summary = "Оплата есть, право на работу нужно сверить";
    }
    stages.push(payment);
  } else {
    stages.push(
      deliverableStage(
        "escalation_package",
        paymentTitle("Дополнительные обращения", e.order),
        e.result,
        e.order.entitlement,
        "open_escalation",
        "open_escalation",
      ),
    );
  }

  stages.push(
    f.closure.state === "unknown"
      ? unknown("closure", "Итог и завершение дела")
      : stage(
          "closure",
          "Итог и завершение дела",
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
            action: f.closure.state === "review_required" ? "review_closure" : "view_history",
          },
        ),
  );

  const allowed = new Set(f.permissions.allowedActions);
  return stages.map((item) =>
    item.action && !allowed.has(item.action) ? { ...item, action: undefined } : item,
  );
}

export function selectCurrentStage(
  stages: StageView[],
  explicitStage?: FunnelStageId,
  opts?: { closed?: boolean },
): FunnelStageId | undefined {
  if (opts?.closed) return "closure";
  if (explicitStage && stages.some((s) => s.id === explicitStage)) {
    return explicitStage;
  }
  const actionable = stages.find((s) => s.status === "needs_action" && s.action);
  if (actionable) return actionable.id;
  const active = stages.find((s) => s.status === "in_progress");
  if (active) return active.id;
  const waiting = stages.find((s) => s.status === "waiting");
  if (waiting) return waiting.id;
  return stages.find((s) => s.status === "not_started" && s.action)?.id;
}

export function stageStatusToShell(
  status: StageStatus,
  opts?: { overdue?: boolean; isCurrent?: boolean },
): FunnelStageState {
  if (opts?.overdue && (status === "needs_action" || status === "waiting" || status === "in_progress")) {
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

/** Совместимость с StageShell: StageView → поля старого FunnelStage. */
export type FunnelStage = {
  id: FunnelStageId;
  label: string;
  state: FunnelStageState;
  reason: string;
  canAct: boolean;
  shortSummary: string;
  status: StageStatus;
  action?: FunnelAction;
  blockers: string[];
};

export function viewsToFunnelStages(
  views: StageView[],
  current: FunnelStageId | undefined,
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
    canAct: Boolean(v.action) && (v.status === "needs_action" || v.status === "not_started" || v.status === "in_progress"),
    shortSummary: v.summary,
    status: v.status,
    action: v.action,
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
