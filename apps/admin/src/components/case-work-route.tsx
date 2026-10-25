"use client";

/** Блок «Работа с делом»: один маршрут 1→2→3, одна primary-кнопка. */

export type WorkRouteStep = {
  id: string;
  title: string;
  status: string;
  status_label?: string;
  result_summary?: string;
  blocker_reason?: string | null;
  needs_specialist?: boolean;
  primary_action?: {
    id: string;
    label: string;
    method?: string;
    path_suffix?: string | null;
  } | null;
  specialist_questions?: string[];
};

export type WorkRoute = {
  steps?: WorkRouteStep[];
  current_step_id?: string;
  primary_action?: WorkRouteStep["primary_action"];
  blocker_reason?: string | null;
  summary_line?: string;
};

type Props = {
  route: WorkRoute | null | undefined;
  busy?: boolean;
  onRequestReview: () => void;
  onRequestPipeline?: () => void;
  /** Нет файлов: шаблон запроса документов в чат (без авто-MAX). */
  onRequestDocsFromClient?: () => void;
  /** Результат проверки документов — у шага 1 (current или done). */
  docsCheckPanel?: React.ReactNode;
};

function statusClass(status: string): string {
  if (status === "done") return "case-work-step--done";
  if (status === "current") return "case-work-step--current";
  if (status === "blocked") return "case-work-step--blocked";
  return "case-work-step--upcoming";
}

export function CaseWorkRoute({
  route,
  busy,
  onRequestReview,
  onRequestPipeline,
  onRequestDocsFromClient,
  docsCheckPanel,
}: Props) {
  if (!route || !route.steps?.length) {
    return (
      <section className="panel case-work-route" aria-labelledby="case-work-title">
        <h2 id="case-work-title">Работа с делом</h2>
        <p className="hint">Маршрут ещё не рассчитан — обновите карточку дела.</p>
        <div className="row-actions">
          <button type="button" disabled={busy} onClick={onRequestReview}>
            Проверить документы
          </button>
        </div>
      </section>
    );
  }

  const primary = route.primary_action;
  function runPrimary() {
    if (!primary) {
      onRequestReview();
      return;
    }
    if (primary.id === "request_docs_check") {
      onRequestReview();
      return;
    }
    if (primary.id === "request_docs_from_client") {
      onRequestDocsFromClient?.();
      return;
    }
    if (primary.id === "request_pipeline" && onRequestPipeline) {
      onRequestPipeline();
    }
  }

  return (
    <section className="panel case-work-route" aria-labelledby="case-work-title">
      <h2 id="case-work-title">Работа с делом</h2>
      <ol className="case-work-steps">
        {route.steps.map((step, index) => {
          const isCurrent = step.id === route.current_step_id;
          const showPrimary = Boolean(isCurrent && primary);
          const showDocsPanel =
            step.id === "docs_check" &&
            docsCheckPanel &&
            (isCurrent || step.status === "done" || step.status === "blocked");
          return (
            <li key={step.id} className={`case-work-step ${statusClass(step.status)}`}>
              <div className="case-work-step-head">
                <span className="case-work-step-num">{index + 1}.</span>
                <strong>{step.title}</strong>
                <span className="hint"> · {step.status_label || step.status}</span>
              </div>
              {step.result_summary ? (
                <p className="hint" style={{ margin: "0.25rem 0 0" }}>
                  {step.result_summary}
                </p>
              ) : null}
              {isCurrent && step.blocker_reason ? (
                <p className="hint warning-inline" style={{ margin: "0.35rem 0 0" }}>
                  {step.blocker_reason}
                </p>
              ) : null}
              {isCurrent &&
              step.id === "facts_review" &&
              (step.specialist_questions?.length ?? 0) > 0 ? (
                <ul className="plain-list" style={{ marginTop: "0.5rem" }}>
                  {(step.specialist_questions ?? []).map((q) => (
                    <li key={q}>{q}</li>
                  ))}
                </ul>
              ) : null}
              {showPrimary ? (
                <div className="row-actions" style={{ marginTop: "0.5rem" }}>
                  <button type="button" disabled={busy} onClick={() => runPrimary()}>
                    {primary!.label}
                  </button>
                </div>
              ) : null}
              {isCurrent && !primary && step.id === "docs_check" ? (
                <div className="row-actions" style={{ marginTop: "0.5rem" }}>
                  <button type="button" disabled={busy} onClick={onRequestReview}>
                    Проверить документы
                  </button>
                </div>
              ) : null}
              {showDocsPanel ? (
                <div style={{ marginTop: "0.75rem" }}>{docsCheckPanel}</div>
              ) : null}
              {!isCurrent && step.status === "upcoming" ? (
                <p className="hint" style={{ margin: "0.25rem 0 0" }}>
                  {step.blocker_reason || "Позже"}
                </p>
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
