"use client";

import { createContext, useContext, type ReactNode } from "react";
import type { FunnelStageId, FunnelStageState } from "@/lib/case-funnel";
import { nextStageId, stageStepNumber } from "@/lib/case-funnel-accordion";
import { StepPrefixContext } from "@/components/step-number";

export type StageNav = {
  labelOf: (id: FunnelStageId) => string;
  open: (id: FunnelStageId) => void;
};

export const StageNavContext = createContext<StageNav | null>(null);

export function StageMark({ state }: { state: FunnelStageState }) {
  if (state === "done") return <span className="funnel-mark funnel-mark--done">✓</span>;
  if (state === "current") return <span className="funnel-mark funnel-mark--current">→</span>;
  if (state === "overdue") return <span className="funnel-mark funnel-mark--overdue">!</span>;
  if (state === "waiting") return <span className="funnel-mark funnel-mark--waiting">…</span>;
  if (state === "blocked") return <span className="funnel-mark funnel-mark--blocked">✕</span>;
  return <span className="funnel-mark">○</span>;
}

export function StageShell({
  id,
  title,
  state,
  reason,
  summary,
  expanded,
  onToggle,
  children,
}: {
  id: string;
  title: string;
  state: FunnelStageState;
  reason: string;
  summary?: string;
  expanded: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  const nav = useContext(StageNavContext);
  const stageId = id.replace(/^funnel-/, "") as FunnelStageId;
  const step = stageStepNumber(stageId);
  const next = nextStageId(stageId);
  const hint = summary || reason;
  const buttonId = `${id}-button`;
  const panelId = `${id}-panel`;
  return (
    <section
      id={id}
      className={`panel funnel-stage funnel-stage--${state}${
        !expanded && state === "done" ? " funnel-stage--done-compact" : ""
      }${expanded ? " funnel-stage--open" : ""}`}
    >
      <h2 className="funnel-stage-heading">
        <button
          id={buttonId}
          type="button"
          className="funnel-stage-toggle"
          onClick={onToggle}
          title={reason}
          aria-expanded={expanded}
          aria-controls={panelId}
        >
          {step > 0 ? <span className="funnel-stage-num">{step}</span> : null}
          <StageMark state={state} />
          <strong>{title}</strong>
          <span className="hint">
            {!expanded && state === "done" ? "готово · " : ""}
            {hint}
          </span>
          <span className="funnel-stage-caret" aria-hidden="true">
            {expanded ? "▾" : "▸"}
          </span>
        </button>
      </h2>
      <div
        id={panelId}
        role="region"
        aria-labelledby={buttonId}
        className="funnel-stage-body"
        hidden={!expanded}
      >
        <StepPrefixContext.Provider value={step > 0 ? String(step) : ""}>
          {children}
        </StepPrefixContext.Provider>
        {nav && next ? (
          <div className="funnel-stage-next">
            <button type="button" className="ghost" onClick={() => nav.open(next)}>
              Далее: {stageStepNumber(next)}. {nav.labelOf(next)} →
            </button>
          </div>
        ) : null}
      </div>
    </section>
  );
}
