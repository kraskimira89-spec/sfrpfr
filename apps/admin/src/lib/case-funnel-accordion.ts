/**
 * Аккордеон ступеней дела: открыта одна ступень.
 * До ручного выбора открыт текущий этап; смена дела сбрасывает выбор.
 */
import { STAGE_IDS, type FunnelStageId } from "./case-funnel-types";

export type StageAccordion = {
  caseId: string;
  touched: boolean;
  open: FunnelStageId | null;
};

export function initialAccordion(caseId: string): StageAccordion {
  return { caseId, touched: false, open: null };
}

export function openStageOf(
  state: StageAccordion,
  caseId: string,
  current: FunnelStageId | null,
): FunnelStageId | null {
  if (state.caseId !== caseId || !state.touched) return current;
  return state.open;
}

export function toggleAccordion(
  state: StageAccordion,
  caseId: string,
  id: FunnelStageId,
  current: FunnelStageId | null,
): StageAccordion {
  const open = openStageOf(state, caseId, current);
  return { caseId, touched: true, open: open === id ? null : id };
}

export function stageStepNumber(id: FunnelStageId): number {
  return STAGE_IDS.indexOf(id) + 1;
}

export function nextStageId(id: FunnelStageId): FunnelStageId | null {
  const idx = STAGE_IDS.indexOf(id);
  return idx >= 0 && idx < STAGE_IDS.length - 1 ? STAGE_IDS[idx + 1] : null;
}
