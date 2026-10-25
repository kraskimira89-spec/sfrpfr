/** Многоуровневая нумерация внутри этапа: 3 → 3.1 → 3.1.1. Без родителя — «1.». */

export function stepLabel(prefix: string, n: number): string {
  return prefix ? `${prefix}.${n}` : `${n}.`;
}

export function childPrefix(prefix: string, n: number): string {
  return prefix ? `${prefix}.${n}` : String(n);
}
