"use client";

import { StepNo, StepScope } from "@/components/step-number";

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
  /** Ручная сверка периодов ИЛС ↔ трудовая (пока нет автоматической). */
  onRecordFactsReview?: (outcome: "discrepancies" | "no_discrepancies") => void;
  /** Открыть другой этап дела (файлы — documents, проект — appeals_documents). */
  onOpenStage?: (stageId: string) => void;
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
  onRecordFactsReview,
  onOpenStage,
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
    if (primary.id === "open_appeals_stage") {
      onOpenStage?.("appeals_documents");
      return;
    }
    if (primary.id === "request_pipeline" && onRequestPipeline) {
      onRequestPipeline();
    }
  }

  const isFactsReview =
    primary?.id === "record_facts_review" || primary?.id === "open_facts_review";

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
                <span className="case-work-step-num">
                  <StepNo n={index + 1} />
                </span>
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
              {showPrimary && isFactsReview ? (
                <div className="row-actions" style={{ marginTop: "0.5rem", flexWrap: "wrap" }}>
                  {onOpenStage ? (
                    <button
                      type="button"
                      className="secondary"
                      disabled={busy}
                      onClick={() => onOpenStage("documents")}
                      title="Открыть файлы клиента: у каждого есть кнопка «Текст»"
                    >
                      Открыть тексты ИЛС и трудовой
                    </button>
                  ) : null}
                  <button
                    type="button"
                    disabled={busy || !onRecordFactsReview}
                    onClick={() => onRecordFactsReview?.("discrepancies")}
                  >
                    Расхождения есть
                  </button>
                  <button
                    type="button"
                    disabled={busy || !onRecordFactsReview}
                    onClick={() => onRecordFactsReview?.("no_discrepancies")}
                  >
                    Расхождений нет
                  </button>
                </div>
              ) : showPrimary ? (
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
                <div style={{ marginTop: "0.75rem" }}>
                  <StepScope n={index + 1}>{docsCheckPanel}</StepScope>
                </div>
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
