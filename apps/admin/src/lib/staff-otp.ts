/** Утилиты 6-значного OTP для входа сотрудника (без хранения в storage). */

export const OTP_LENGTH = 6;

export function normalizeOtpDigits(value: string): string {
  return value.replace(/\D/g, "").slice(0, OTP_LENGTH);
}

export function splitOtpDigits(code: string): string[] {
  const normalized = normalizeOtpDigits(code);
  const cells = Array.from({ length: OTP_LENGTH }, (_, index) => normalized[index] ?? "");
  return cells;
}

export function mergeOtpDigits(cells: readonly string[]): string {
  return normalizeOtpDigits(cells.join(""));
}

export function isOtpComplete(code: string): boolean {
  return normalizeOtpDigits(code).length === OTP_LENGTH;
}

export function formatResendCountdown(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export function getOtpSubmitLabel(options: { busy: boolean; complete: boolean }): string {
  if (options.busy) return "Проверяем код…";
  if (!options.complete) return "Введите код";
  return "Войти в кабинет";
}
