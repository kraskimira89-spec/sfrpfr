export type DashboardQueueKey =
  | "new"
  | "docs"
  | "conflicts"
  | "reply"
  | "today"
  | "sla"
  | "urgent"
  | "payment"
  | "all"
  | `doc:${string}`;

export type QueueWorkItem = {
  case_id: string;
  client_name: string | null;
  priority: "urgent" | "today" | "standard";
  pipeline_status: string;
  b2c_status: string;
  waiting_on: string;
  last_event: string;
  next_action: string;
  next_action_at: string | null;
  deadline_status: "overdue" | "soon" | "today" | "ok" | "waiting";
  channel: string;
  max_linked?: boolean;
  web_linked?: boolean;
  channel_conflict?: boolean;
  conflict_kind?: string | null;
  conflict_detail?: string | null;
  doc_flags?: Record<string, boolean>;
  waiting_days?: number;
};

const QUEUE_KEYS = new Set([
  "new",
  "docs",
  "conflicts",
  "reply",
  "today",
  "sla",
  "urgent",
  "payment",
  "all",
]);

export function parseDashboardQueueParam(raw: string | null | undefined): DashboardQueueKey | null {
  const value = (raw || "").trim();
  if (!value) return null;
  if (QUEUE_KEYS.has(value)) return value as DashboardQueueKey;
  if (value.startsWith("doc:") && value.length > 4) return value as DashboardQueueKey;
  return null;
}

export function filterWorkQueue(
  items: QueueWorkItem[],
  queue: DashboardQueueKey | string,
): QueueWorkItem[] {
  return items.filter((item) => {
    if (queue === "all") return true;
    if (queue === "urgent") return item.priority === "urgent";
    if (queue === "today") {
      return item.priority === "today" || item.deadline_status === "today";
    }
    if (queue === "reply") return item.waiting_on === "staff";
    if (queue === "docs") {
      return item.waiting_on === "client" || item.waiting_on === "archive";
    }
    if (queue === "payment") return item.waiting_on === "payment";
    if (queue === "sla") return item.deadline_status === "overdue";
    if (queue === "new") {
      return item.pipeline_status === "intake" || item.b2c_status === "lead";
    }
    if (queue === "conflicts") return Boolean(item.channel_conflict);
    if (queue.startsWith("doc:")) {
      const key = queue.slice(4);
      return Boolean(item.doc_flags?.[key]);
    }
    return true;
  });
}
