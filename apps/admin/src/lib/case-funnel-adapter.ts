import {
  STAGE_IDS,
  STAGE_TITLES,
  type ActionId,
  type FunnelFacts,
  type FunnelView,
  type OrderFacts,
  type StageId,
  type StageStatus,
  type StageView,
  type WorkFacts,
} from "./case-funnel-types";

function view(
  id: StageId,
  status: StageStatus,
  summary: string,
  options: {
    action?: ActionId;
    blockers?: readonly string[];
    dueAt?: string;
  } = {},
): StageView {
  return {
    id,
    title: STAGE_TITLES[id],
    status,
    summary,
    blockers: options.blockers ?? [],
    action: options.action,
    dueAt: options.dueAt,
  };
}

function payment(
  id: StageId,
  order: OrderFacts,
  prerequisite: "ready" | "blocked" | "not_required" | "unknown",
  action: ActionId,
): StageView {
  const labels: Record<OrderFacts["state"], string> = {
    unknown: "Статус заказа или оплаты недоступен",
    not_ordered: "Заказ не оформлен",
    pending: "Ожидается оплата",
    paid: "Оплата подтверждена",
    canceled: "Заказ отменён",
    refunded: "Возврат подтверждён",
  };

  let status: StageStatus;

  switch (order.state) {
    case "paid":
      status = "done";
      break;
    case "pending":
      status = "waiting";
      break;
    case "canceled":
    case "refunded":
      status = "needs_action";
      break;
    case "unknown":
      status = "unknown";
      break;
    default:
      status =
        prerequisite === "ready"
          ? "not_started"
          : prerequisite === "not_required"
            ? "not_required"
            : prerequisite === "unknown"
              ? "unknown"
              : "blocked";
  }

  const amount = order.amountRub;
  const title =
    amount !== undefined && Number.isFinite(amount) && amount > 0
      ? `${STAGE_TITLES[id]} · ${amount.toLocaleString("ru-RU")} ₽`
      : STAGE_TITLES[id];

  return {
    ...view(
      id,
      status,
      status === "not_required" ? "Услуга не требуется" : labels[order.state],
      {
        action:
          status === "blocked" || status === "not_required" ? undefined : action,
        blockers:
          status === "blocked"
            ? ["Не выполнены условия согласования услуги"]
            : [],
      },
    ),
    title,
  };
}

function work(
  id: StageId,
  facts: WorkFacts,
  entitlement: OrderFacts["entitlement"],
  action: ActionId,
): StageView {
  if (facts.state === "delivered") {
    return view(id, "done", "Передача результата подтверждена", { action });
  }

  if (facts.state === "unknown") {
    return view(id, "unknown", "Состояние результата недоступно");
  }

  if (entitlement !== "granted") {
    return view(
      id,
      entitlement === "unknown" ? "unknown" : "blocked",
      "Право на выполнение услуги не подтверждено",
      { blockers: ["Нужно проверить заказ и право на услугу"] },
    );
  }

  if (facts.state === "ready") {
    return view(
      id,
      "needs_action",
      facts.releaseReady === "yes"
        ? "Результат готов к передаче"
        : "Нужна проверка или согласование результата",
      { action },
    );
  }

  return view(
    id,
    facts.state === "working" ? "in_progress" : "not_started",
    facts.state === "working" ? "Идёт подготовка" : "Можно начать работу",
    { action },
  );
}

function consentPrerequisite(
  need: FunnelFacts["appeals"]["need"],
  consent: FunnelFacts["appeals"]["consent"],
): "ready" | "blocked" | "not_required" | "unknown" {
  if (need === "not_needed" || consent === "declined") return "not_required";
  if (need === "unknown" || consent === "unknown") return "unknown";
  return consent === "accepted" ? "ready" : "blocked";
}

export function buildFunnel(f: FunnelFacts): FunnelView {
  const s = {} as Record<StageId, StageView>;

  s.contact_consents = view(
    "contact_consents",
    f.contact === "unknown"
      ? "unknown"
      : f.contact === "complete"
        ? "done"
        : "needs_action",
    f.contact === "complete"
      ? "Контакты и обязательные согласия подтверждены"
      : "Проверить контакты и необходимые согласия",
    { action: "edit_contacts" },
  );

  const documentStatuses = {
    unknown: "unknown",
    missing: "not_started",
    processing: "in_progress",
    needs_action: "needs_action",
    ready: "done",
  } as const;

  s.documents = view(
    "documents",
    documentStatuses[f.documents],
    {
      unknown: "Данные документов недоступны",
      missing: "Нужны документы",
      processing: "Идёт обработка файлов",
      needs_action: "Нужно уточнить комплект или качество",
      ready: "Комплект для текущей проверки подготовлен",
    }[f.documents],
    { action: "upload_documents" },
  );

  const p = f.precheck;

  if (p.state === "queued" || p.state === "running") {
    s.precheck_summary = view(
      "precheck_summary",
      p.state === "queued" ? "waiting" : "in_progress",
      p.state === "queued" ? "Проверка в очереди" : "Идёт проверка",
      { action: "view_precheck" },
    );
  } else if (p.stale || p.state === "failed") {
    s.precheck_summary = view(
      "precheck_summary",
      "needs_action",
      p.stale ? "Результат устарел" : "Проверка не завершена",
      { action: "run_precheck" },
    );
  } else if (p.state === "completed") {
    // Зелёный этап — после отправки краткого резюме клиенту (summaryDelivery=confirmed),
    // а не только когда outcome=clear: расхождения тоже закрываются отправкой резюме.
    const summaryDone = p.summaryDelivery === "confirmed";
    s.precheck_summary = view(
      "precheck_summary",
      summaryDone
        ? "done"
        : p.outcome === "unknown"
          ? "unknown"
          : "needs_action",
      summaryDone
        ? {
            unknown: "Краткое резюме отправлено клиенту",
            clear: "Резюме отправлено · расхождений не найдено",
            discrepancies: "Резюме отправлено · найдены расхождения",
            clarify: "Резюме отправлено · нужно уточнение комплекта",
          }[p.outcome]
        : {
            unknown: "Нужно проверить результат",
            clear: "В проверенном объёме расхождений не найдено",
            discrepancies: "Найдены расхождения между источниками",
            clarify: "Нужно уточнение или ручной разбор",
          }[p.outcome],
      {
        action:
          !summaryDone &&
          p.outcome !== "unknown" &&
          (p.summaryDelivery === "not_sent" || p.summaryDelivery === "unknown")
            ? "send_summary"
            : "view_precheck",
      },
    );
  } else {
    s.precheck_summary = view(
      "precheck_summary",
      p.state === "unknown"
        ? "unknown"
        : f.documents === "ready"
          ? "not_started"
          : "blocked",
      "Проверка ещё не подтверждена",
      {
        action: f.documents === "ready" ? "run_precheck" : undefined,
      },
    );
  }

  s.analysis_payment = payment(
    "analysis_payment",
    f.analysis.order,
    p.stale
      ? "blocked"
      : f.analysis.need === "recommended"
        ? "ready"
        : f.analysis.need === "not_needed"
          ? "not_required"
          : "unknown",
    "open_analysis_order",
  );

  s.full_analysis = work(
    "full_analysis",
    f.analysis.work,
    f.analysis.order.entitlement,
    "open_analysis",
  );

  const a = f.appeals;
  const appealPrerequisite = consentPrerequisite(a.need, a.consent);

  s.appeals_consent = view(
    "appeals_consent",
    appealPrerequisite === "ready"
      ? "done"
      : appealPrerequisite === "not_required"
        ? "not_required"
        : appealPrerequisite === "unknown"
          ? "unknown"
          : a.consent === "pending"
            ? "waiting"
            : "needs_action",
    appealPrerequisite === "ready"
      ? "Объём работ согласован"
      : appealPrerequisite === "not_required"
        ? "Этап не требуется или клиент отказался"
        : "Нужно согласовать план и состав обращений",
    {
      action:
        a.need === "recommended" &&
        a.consent !== "accepted" &&
        a.consent !== "declined"
          ? "request_appeals_consent"
          : undefined,
    },
  );

  s.appeals_payment = payment(
    "appeals_payment",
    a.order,
    appealPrerequisite,
    "open_appeals_order",
  );

  s.appeals_documents = work(
    "appeals_documents",
    a.work,
    a.order.entitlement,
    "open_appeals",
  );

  if (f.submission === "confirmed") {
    s.submission = view("submission", "done", "Подача подтверждена", {
      action: "record_submission",
    });
  } else if (f.submission === "help_requested") {
    s.submission = view(
      "submission",
      "needs_action",
      "Клиенту нужна помощь с подачей",
      { action: "schedule_call" },
    );
  } else if (f.submission === "unknown") {
    s.submission = view("submission", "unknown", "Сведения о подаче недоступны");
  } else {
    const delivered = a.work.state === "delivered";

    s.submission = view(
      "submission",
      delivered ? "waiting" : "blocked",
      delivered
        ? "Уточнить, поданы ли документы"
        : "Согласованный пакет ещё не передан клиенту",
      { action: delivered ? "record_submission" : undefined },
    );
  }

  const follow = f.followUp;

  s.follow_up = view(
    "follow_up",
    follow.state === "unknown"
      ? "unknown"
      : follow.state === "completed"
        ? "done"
        : f.submission !== "confirmed"
          ? "blocked"
          : follow.callRequired
            ? "needs_action"
            : follow.state === "active"
              ? "in_progress"
              : "waiting",
    follow.state === "completed"
      ? "Цикл контроля завершён"
      : f.submission !== "confirmed"
        ? "Нет подтверждённой подачи"
        : follow.callRequired
          ? "Нужно уточнить состояние дела звонком"
          : follow.state === "paused"
            ? "Контроль приостановлен"
            : "Проверить текущее состояние рассмотрения",
    {
      action:
        f.submission === "confirmed" &&
        follow.state !== "unknown" &&
        follow.state !== "completed"
          ? follow.callRequired
            ? "schedule_call"
            : "record_follow_up"
          : undefined,
      dueAt: follow.dueAt,
    },
  );

  const responseStatuses = {
    unknown: "unknown",
    none: "waiting",
    received: "needs_action",
    reviewing: "in_progress",
    reviewed: "done",
  } as const;

  s.response_review = view(
    "response_review",
    responseStatuses[f.response],
    {
      unknown: "Сведения об ответе недоступны",
      none: "Ответ пока не зарегистрирован",
      received: "Получен документ — нужен разбор",
      reviewing: "Идёт разбор ответа",
      reviewed: "Разбор выполнен, следующий шаг зафиксирован",
    }[f.response],
    {
      action:
        f.response === "received" ||
        f.response === "reviewing" ||
        f.response === "reviewed"
          ? "review_response"
          : undefined,
    },
  );

  const e = f.escalation;
  const extraPrerequisite = consentPrerequisite(e.need, e.consent);

  if (e.work.state === "delivered") {
    s.escalation_package = work(
      "escalation_package",
      e.work,
      e.order.entitlement,
      "open_escalation",
    );
  } else if (e.order.entitlement === "granted") {
    s.escalation_package = work(
      "escalation_package",
      e.work,
      e.order.entitlement,
      "open_escalation",
    );
  } else if (e.order.state !== "not_ordered") {
    const paymentView = payment(
      "escalation_package",
      e.order,
      extraPrerequisite,
      "open_escalation",
    );

    s.escalation_package =
      paymentView.status === "done"
        ? {
            ...paymentView,
            status: "needs_action",
            summary: "Оплата подтверждена; право на выполнение нужно сверить",
          }
        : paymentView;
  } else if (extraPrerequisite === "not_required") {
    s.escalation_package = view(
      "escalation_package",
      "not_required",
      "Дополнительная работа не требуется или не заказана",
    );
  } else if (extraPrerequisite === "unknown") {
    s.escalation_package = view(
      "escalation_package",
      "unknown",
      "Необходимость или согласование пока не определены",
    );
  } else {
    s.escalation_package = view(
      "escalation_package",
      "needs_action",
      extraPrerequisite === "ready"
        ? "Можно перейти к оформлению услуги"
        : "Нужно согласовать основания и объём работ",
      { action: "open_escalation" },
    );
  }

  s.closure = view(
    "closure",
    f.closure.state === "closed"
      ? "done"
      : f.closure.state === "review_required"
        ? "needs_action"
        : f.closure.state === "unknown"
          ? "unknown"
          : "not_started",
    f.closure.state === "closed"
      ? f.closure.reason || "Завершение дела подтверждено"
      : "Дело остаётся открытым",
    {
      action: f.closure.state === "review_required" ? "review_closure" : undefined,
    },
  );

  const allowed = new Set(f.allowedActions);

  const stages = STAGE_IDS.map((id) => {
    const item = s[id];
    return item.action && !allowed.has(item.action)
      ? { ...item, action: undefined }
      : item;
  });

  // Текущий этап маршрута — первый незавершённый по порядку 1→13.
  // Срочная задача (priority) не подменяет позицию дела в цепочке.
  const routeCurrent =
    f.closure.state === "closed"
      ? ("closure" as StageId)
      : (STAGE_IDS.map((id) => stages.find((item) => item.id === id)).find((item) => {
          if (!item) return false;
          if (item.status === "done" || item.status === "not_required") return false;
          if (item.status === "blocked" || item.status === "unknown") return false;
          return (
            item.status === "needs_action" ||
            item.status === "in_progress" ||
            item.status === "waiting" ||
            (item.status === "not_started" && Boolean(item.action))
          );
        })?.id ?? null);

  const priorityStageId = pickPriorityStage(f, stages, routeCurrent);

  return { stages, currentStageId: routeCurrent, priorityStageId };
}

/**
 * Срочная задача ≠ текущий этап маршрута.
 * Пример: ответ СФР пришёл, пока ещё не закрыта подача — route на submission/follow_up,
 * priority = response_review.
 */
function pickPriorityStage(
  f: FunnelFacts,
  stages: readonly StageView[],
  routeCurrent: StageId | null,
): StageId | null {
  const exists = (id: StageId) => stages.some((s) => s.id === id);
  if (f.preferredStageId && exists(f.preferredStageId)) {
    return f.preferredStageId === routeCurrent ? null : f.preferredStageId;
  }
  // Ответ СФР требует разбора — срочно, даже если маршрут ещё на контроле/подаче.
  if (
    (f.response === "received" || f.response === "reviewing") &&
    exists("response_review") &&
    routeCurrent !== "response_review" &&
    routeCurrent !== "closure"
  ) {
    return "response_review";
  }
  // Устаревшая проверка при уже оплаченном анализе — вернуться к сверке, не к оплате.
  if (
    f.precheck.stale &&
    f.analysis.order.state === "paid" &&
    exists("precheck_summary") &&
    routeCurrent !== "precheck_summary"
  ) {
    return "precheck_summary";
  }
  return null;
}

export type ActionHandlers = Partial<Record<ActionId, () => void>>;

export function executeStageAction(
  stage: StageView,
  handlers: ActionHandlers,
): void {
  if (!stage.action) return;
  const handler = handlers[stage.action];
  if (!handler) return;
  handler();
}
