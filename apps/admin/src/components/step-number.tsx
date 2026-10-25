"use client";

import { createContext, useContext, type ReactNode } from "react";
import { childPrefix, stepLabel } from "@/lib/step-number";

/** Номер родителя для вложенных шагов («3» в этапе 3, «3.1» в его первом шаге). */
export const StepPrefixContext = createContext<string>("");

export function StepNo({ n }: { n: number }) {
  const prefix = useContext(StepPrefixContext);
  return <span className="step-no">{stepLabel(prefix, n)}</span>;
}

/** Вложенный уровень: дети шага n нумеруются n.1, n.2… */
export function StepScope({ n, children }: { n: number; children: ReactNode }) {
  const prefix = useContext(StepPrefixContext);
  return (
    <StepPrefixContext.Provider value={childPrefix(prefix, n)}>{children}</StepPrefixContext.Provider>
  );
}
