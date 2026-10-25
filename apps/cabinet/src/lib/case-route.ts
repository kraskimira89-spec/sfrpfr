/** Клиентские главы маршрута поверх work.stages / status_key (без нового backend). */

export type RouteChapterId =
  | "intro"
  | "documents"
  | "review"
  | "plan"
  | "outcome";

export type RouteChapter = {
  id: RouteChapterId;
  label: string;
  state: "done" | "current" | "todo";
};

export type RouteDocMark = {
  key: string;
  title: string;
  mark: "done" | "need" | "checking" | "fix" | "optional";
  statusText: string;
  purpose?: string;
};

export type RouteNextStep = {
  mode: "action" | "waiting";
  title: string;
  why: string;
  primaryLabel: string | null;
  howtoUrl: string | null;
  howtoLabel: string | null;
};

export type RouteEvent = {
  when: string;
  text: string;
};

export type ClientWorkLike = {
  status_key: string;
  status_label: string;
  status_hint: string;
  now_need: string;
  cta_key: string;
  cta_label: string;
  required_uploaded: number;
  required_total: number;
  stages: { n: number; title: string; hint: string; state: string }[];
  documents: {
    key: string;
    title: string;
    need: string;
    status: string;
    status_label: string;
    added_at?: string | null;
  }[];
  next_actions: string[];
  ils_howto_url: string;
};

const CHAPTER_META: { id: RouteChapterId; label: string; stageN: number }[] = [
  { id: "intro", label: "Знакомство", stageN: 1 },
  { id: "documents", label: "Документы", stageN: 2 },
  { id: "review", label: "Проверка", stageN: 3 },
  { id: "plan", label: "План действий", stageN: 4 },
  { id: "outcome", label: "Итоги", stageN: 5 },
];

const DOC_PURPOSE: Record<string, string> = {
  ils: "Нужна, чтобы сопоставить периоды работы и сведения о пенсионных правах.",
  labor: "Нужна для построчной сверки с выпиской о состоянии лицевого счёта.",
  archive: "Подтверждает периоды, если организация уже не существует.",
  passport: "Для сверки установочных данных, если специалист попросит.",
};

export function chaptersFromWork(work: ClientWorkLike): RouteChapter[] {
  const byN = new Map(work.stages.map((s) => [s.n, s]));
  return CHAPTER_META.map((meta) => {
    const stage = byN.get(meta.stageN);
    const state =
      stage?.state === "done" || stage?.state === "current" || stage?.state === "todo"
        ? stage.state
        : "todo";
    return { id: meta.id, label: meta.label, state };
  });
}

export function currentChapterId(work: ClientWorkLike): RouteChapterId {
  const chapters = chaptersFromWork(work);
  const current = chapters.find((c) => c.state === "current");
  if (current) return current.id;
  if (work.status_key === "consent") return "intro";
  if (work.status_key === "waiting_docs" || work.status_key === "need_info") return "documents";
  if (work.status_key === "docs_review" || work.status_key === "diagnosis") return "review";
  if (work.status_key === "result_ready") return "plan";
  if (work.status_key === "done") return "outcome";
  return "documents";
}

export function chapterTitle(id: RouteChapterId): { heading: string; lead: string } {
  switch (id) {
    case "intro":
      return {
        heading: "Знакомство",
        lead: "Сохраним необходимые сведения и согласие, чтобы можно было работать с документами.",
      };
    case "documents":
      return {
        heading: "Собираем документы",
        lead: "Подготовим сведения для проверки вашего стажа.",
      };
    case "review":
      return {
        heading: "Разбираемся в стаже",
        lead: "Специалист проверяет комплект. От вас сейчас может ничего не требоваться.",
      };
    case "plan":
      return {
        heading: "Готовим следующие действия",
        lead: "Посмотрите итог проверки и предложенный план.",
      };
    case "outcome":
      return {
        heading: "Подводим итоги",
        lead: "Зафиксирован результат работы по документам. Решение о пенсии принимает СФР.",
      };
  }
}

function firstActionSlot(work: ClientWorkLike) {
  return (
    work.documents.find(
      (row) => row.need === "required" && (row.status === "missing" || row.status === "reupload"),
    ) ||
    work.documents.find((row) => row.status === "reupload") ||
    null
  );
}

export function nextStepFromWork(work: ClientWorkLike): RouteNextStep {
  const waiting =
    work.next_actions.length === 0 && (work.cta_key === "wait" || work.cta_key === "upload");
  if (waiting || work.cta_key === "wait") {
    return {
      mode: "waiting",
      title: "Сейчас работает специалист",
      why: "От вас ничего не требуется. Дополнительные документы пока не нужны.",
      primaryLabel: null,
      howtoUrl: null,
      howtoLabel: null,
    };
  }

  const slot = firstActionSlot(work);
  const why =
    (slot && DOC_PURPOSE[slot.key]) ||
    work.status_hint ||
    "Это поможет специалисту продолжить проверку.";

  let howtoUrl: string | null = null;
  let howtoLabel: string | null = null;
  if (slot?.key === "ils" || /илс|выписк/i.test(work.now_need)) {
    howtoUrl = work.ils_howto_url;
    howtoLabel = "Где получить документ?";
  }

  return {
    mode: "action",
    title: work.now_need,
    why,
    primaryLabel: work.cta_label,
    howtoUrl,
    howtoLabel,
  };
}

export function kitMarksFromWork(work: ClientWorkLike): RouteDocMark[] {
  const visible = work.documents.filter((row) => {
    if (row.need === "required") return true;
    if (row.status === "reupload" || row.status === "awaiting" || row.status === "accepted") {
      return true;
    }
    if (row.status === "staff_requested") return true;
    return false;
  });

  return visible.map((row) => {
    let mark: RouteDocMark["mark"] = "optional";
    if (row.status === "accepted") mark = "done";
    else if (row.status === "awaiting") mark = "checking";
    else if (row.status === "reupload") mark = "fix";
    else if (row.status === "missing" && row.need === "required") mark = "need";
    else if (row.status === "staff_requested") mark = "need";

    let statusText = row.status_label;
    if (row.status === "awaiting") {
      statusText = "Документ получен. Проверим его пригодность";
    } else if (row.status === "accepted") {
      statusText = "Принят для текущего этапа";
    } else if (row.status === "reupload") {
      statusText = row.status_label;
    }

    return {
      key: row.key,
      title: row.title,
      mark,
      statusText,
      purpose: DOC_PURPOSE[row.key],
    };
  });
}

export function recentEventsFromWork(work: ClientWorkLike, limit = 5): RouteEvent[] {
  const events: RouteEvent[] = [];
  for (const row of work.documents) {
    if (!row.added_at) continue;
    if (row.status === "awaiting") {
      events.push({ when: row.added_at, text: `Вы добавили: ${row.title}` });
    } else if (row.status === "accepted") {
      events.push({ when: row.added_at, text: `Принят документ: ${row.title}` });
    } else if (row.status === "reupload") {
      events.push({ when: row.added_at, text: `Нужна замена: ${row.title}` });
    }
  }
  return events.slice(0, limit);
}

export function requiredProgressLabel(work: ClientWorkLike): string | null {
  if (work.required_total <= 0) return null;
  return `Обязательных документов: ${work.required_uploaded} из ${work.required_total}`;
}
