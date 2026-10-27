/** Таймаут клиентского ожидания черновика этапа 5 (YC DeepSeek часто >60–90 с). */
export const FULL_ANALYSIS_DRAFT_TIMEOUT_MS = 180_000;

/** Сколько раз по 2 с опрашивать state после обрыва ответа. */
export const FULL_ANALYSIS_DRAFT_RECOVER_POLLS = 15;

export type FullAnalysisVersionSnap = {
  id?: string | null;
  n?: number | null;
  status?: string | null;
  markdown?: string | null;
};

export function isAbortLikeError(error: unknown): boolean {
  if (error instanceof DOMException && error.name === "AbortError") return true;
  if (!(error instanceof Error)) return false;
  const msg = error.message.toLowerCase();
  return (
    error.name === "AbortError" ||
    msg.includes("aborted") ||
    msg.includes("timeout") ||
    msg.includes("превышено время") ||
    msg.includes("время ожидания")
  );
}

/**
 * Если клиент не дождался ответа draft, на сервере версия уже могла появиться.
 * Тогда подставляем её вместо повторной генерации.
 */
export function reconcileDraftAfterClientFailure(args: {
  beforeId: string | null | undefined;
  after: FullAnalysisVersionSnap | null | undefined;
}): { recovered: boolean; markdown: string; notice: string } {
  const after = args.after;
  if (!after?.id) {
    return { recovered: false, markdown: "", notice: "" };
  }
  const isNew = after.id !== args.beforeId;
  const usable =
    after.status === "draft" ||
    after.status === "staff_reviewed" ||
    after.status === "remarks";
  const md = String(after.markdown || "").trim();
  if (isNew && usable && md) {
    return {
      recovered: true,
      markdown: md,
      notice:
        "Ответ на клиенте не дождались, но новая версия уже есть на сервере — подставил её. Проверьте перед выдачей; повторную генерацию не запускал.",
    };
  }
  return { recovered: false, markdown: "", notice: "" };
}

export function draftTimeoutMessage(timeoutMs: number): string {
  const sec = Math.round(timeoutMs / 1000);
  return `Превышено время ожидания ИИ (${sec} с). Проверьте, не появилась ли версия на сервере, или повторите.`;
}
