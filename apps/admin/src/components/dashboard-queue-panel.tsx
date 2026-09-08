"use client";

import {
  filterWorkQueue,
  type DashboardQueueKey,
  type QueueWorkItem,
} from "@/lib/dashboard-queue";
import { caseCatalogLabel } from "@/components/cases-registry";
import { labelPipeline } from "@/lib/ui-labels";

const QUEUE_TITLES: Record<string, string> = {
  new: "Новые обращения",
  docs: "Ожидаем документы",
  conflicts: "Конфликты каналов",
  reply: "Требуют моего ответа",
  today: "Дедлайн сегодня",
  sla: "Риск SLA",
  urgent: "Срочные",
  payment: "Ожидаем оплату",
  all: "Рабочая очередь",
};

const CHANNEL_LABELS: Record<string, string> = {
  max_miniapp: "MAX",
  web_cabinet: "Веб-кабинет",
  unset: "не выбран",
};

const PRIORITY_LABELS: Record<string, string> = {
  urgent: "Срочно",
  today: "Сегодня",
  standard: "Стандартно",
};

function queueCanon(queue: string): { title: string; steps: string[] } {
  if (queue === "new") {
    return {
      title: "Что сделать по новым обращениям",
      steps: [
        "Откройте чат и ответьте в течение часа с момента заявки.",
        "Уточните ситуацию кнопками / коротким вопросом — не просите сканы в MAX.",
        "Документы — только через «Мои документы» в кабинете на сайте.",
        "После первого контакта переведите дело из lead/intake в работу.",
      ],
    };
  }
  if (queue === "docs") {
    return {
      title: "Что сделать, пока ждём документы",
      steps: [
        "Посмотрите «Следующий шаг» и флаги документов (ИЛС, трудовая, архив).",
        "Напомните клиенту в том же чате (MAX или кабинет) — без приёма сканов в переписку.",
        "Если ждём архивную справку — зафиксируйте срок и канал напоминания.",
        "После загрузки документов откройте дело и проверьте комплект.",
      ],
    };
  }
  if (queue === "conflicts") {
    return {
      title: "Как снять конфликт каналов",
      steps: [
        "Прочитайте «Суть конфликта» в строке дела.",
        "Предпочтение MAX без привязки: попросите клиента нажать «Начать» в личном боте или привяжите MAX в карточке.",
        "Предпочтение веб без аккаунта: отправьте ссылку на кабинет и помогите войти (почта / код MAX).",
        "Если канал выбран ошибочно — смените предпочтение в карточке клиента.",
      ],
    };
  }
  if (queue === "reply" || queue === "sla") {
    return {
      title: "Что сделать, когда ждут ответа сотрудника",
      steps: [
        "Откройте чат и ответьте клиенту в том же деле.",
        "Обновите «следующий шаг» и waiting_on после ответа.",
        "Не считайте ожиданием «без ответа» паузу на архив / СФР / документы клиента.",
      ],
    };
  }
  if (queue === "today") {
    return {
      title: "Дедлайны на сегодня",
      steps: [
        "Разберите срочные строки сверху вниз.",
        "Сначала ответьте клиенту, затем закройте внутренние задачи.",
      ],
    };
  }
  return {
    title: "Рекомендации по очереди",
    steps: ["Откройте дело и выполните указанный следующий шаг."],
  };
}

function formatWhen(value: string | null | undefined): string {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return "—";
  return dt.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function DashboardQueuePanel({
  queue,
  items,
  onBack,
  onOpenCase,
  busy = false,
}: {
  queue: DashboardQueueKey | string;
  items: QueueWorkItem[];
  onBack: () => void;
  onOpenCase: (caseId: string) => void;
  busy?: boolean;
}) {
  const filtered = filterWorkQueue(items, queue);
  const title =
    QUEUE_TITLES[queue] || (queue.startsWith("doc:") ? "Статус документов" : "Очередь");
  const canon = queueCanon(queue);
  const showConflict = queue === "conflicts";

  return (
    <section className="stack dashboard-queue">
      <div className="dashboard-queue__head">
        <button type="button" className="ghost" onClick={onBack}>
          ← К дашборду
        </button>
        <h1>{title}</h1>
        <p className="lead lead-compact">
          В очереди: <strong>{filtered.length}</strong>. Ниже — рекомендация и список дел с
          следующим шагом.
        </p>
      </div>

      <div className="panel dashboard-queue__recs" role="note">
        <h2>{canon.title}</h2>
        <ol className="dashboard-queue__steps">
          {canon.steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </div>

      <div className="panel">
        <h2>Список дел</h2>
        {filtered.length === 0 ? (
          <p className="hint">Сейчас пусто — можно вернуться к дашборду.</p>
        ) : (
          <div className="queue-wrap">
            <table className="queue-table">
              <thead>
                <tr>
                  <th>Приоритет</th>
                  <th>Дело</th>
                  <th>Этап</th>
                  <th>Последнее событие</th>
                  <th>Следующий шаг</th>
                  {showConflict ? <th>Суть конфликта</th> : null}
                  <th>Дедлайн</th>
                  <th>Канал</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.case_id} className={`tone-${item.deadline_status}`}>
                    <td>{PRIORITY_LABELS[item.priority] ?? item.priority}</td>
                    <td>
                      <strong>{item.client_name ?? "Клиент"}</strong>
                      <div className="hint">{caseCatalogLabel(item.case_id)}</div>
                    </td>
                    <td>{labelPipeline(item.pipeline_status)}</td>
                    <td>{item.last_event}</td>
                    <td>{item.next_action}</td>
                    {showConflict ? (
                      <td className="dashboard-queue__conflict">
                        {item.conflict_detail || "—"}
                      </td>
                    ) : null}
                    <td>
                      <span className={`deadline deadline--${item.deadline_status}`}>
                        {formatWhen(item.next_action_at)}
                      </span>
                    </td>
                    <td>{CHANNEL_LABELS[item.channel] ?? item.channel}</td>
                    <td>
                      <button
                        type="button"
                        className="ghost"
                        disabled={busy}
                        onClick={() => onOpenCase(item.case_id)}
                      >
                        Открыть
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
