"use client";

import {
  ClipboardEvent,
  KeyboardEvent,
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
} from "react";
import {
  OTP_LENGTH,
  mergeOtpDigits,
  normalizeOtpDigits,
  splitOtpDigits,
} from "@/lib/staff-otp";

export type StaffOtpInputHandle = {
  focusFirst: () => void;
};

type StaffOtpInputProps = {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  invalid?: boolean;
  autoFocus?: boolean;
};

export const StaffOtpInput = forwardRef<StaffOtpInputHandle, StaffOtpInputProps>(
  function StaffOtpInput({ value, onChange, disabled = false, invalid = false, autoFocus = false }, ref) {
    const cells = splitOtpDigits(value);
    const inputRefs = useRef<(HTMLInputElement | null)[]>([]);
    const didAutoFocus = useRef(false);

    function focusCell(index: number) {
      const safeIndex = Math.max(0, Math.min(index, OTP_LENGTH - 1));
      const el = inputRefs.current[safeIndex];
      el?.focus();
      el?.select();
    }

    useImperativeHandle(ref, () => ({
      focusFirst: () => focusCell(0),
    }));

    useEffect(() => {
      if (!autoFocus || didAutoFocus.current) return;
      didAutoFocus.current = true;
      const firstEmpty = splitOtpDigits(value).findIndex((cell) => !cell);
      focusCell(firstEmpty >= 0 ? firstEmpty : 0);
      // eslint-disable-next-line react-hooks/exhaustive-deps -- autofocus only on mount
    }, [autoFocus]);

    function applyDigits(nextDigits: string) {
      const normalized = normalizeOtpDigits(nextDigits);
      onChange(normalized);
      if (normalized.length < OTP_LENGTH) {
        focusCell(normalized.length);
      } else {
        focusCell(OTP_LENGTH - 1);
      }
    }

    function handleChange(index: number, raw: string) {
      const digits = normalizeOtpDigits(raw);
      if (!digits) {
        const next = [...cells];
        next[index] = "";
        onChange(mergeOtpDigits(next));
        return;
      }
      if (digits.length > 1) {
        applyDigits(digits);
        return;
      }
      const next = [...cells];
      next[index] = digits;
      onChange(mergeOtpDigits(next));
      if (index < OTP_LENGTH - 1) {
        focusCell(index + 1);
      }
    }

    function handleKeyDown(index: number, event: KeyboardEvent<HTMLInputElement>) {
      if (event.key === "Backspace") {
        event.preventDefault();
        if (cells[index]) {
          const next = [...cells];
          next[index] = "";
          onChange(mergeOtpDigits(next));
          return;
        }
        if (index > 0) {
          const next = [...cells];
          next[index - 1] = "";
          onChange(mergeOtpDigits(next));
          focusCell(index - 1);
        }
        return;
      }
      if (event.key === "ArrowLeft" && index > 0) {
        event.preventDefault();
        focusCell(index - 1);
      }
      if (event.key === "ArrowRight" && index < OTP_LENGTH - 1) {
        event.preventDefault();
        focusCell(index + 1);
      }
    }

    function handlePaste(event: ClipboardEvent<HTMLInputElement>) {
      event.preventDefault();
      const pasted = normalizeOtpDigits(event.clipboardData.getData("text"));
      if (!pasted) return;
      applyDigits(pasted);
    }

    return (
      <div className="auth-otp" role="group" aria-label={`Код из ${OTP_LENGTH} цифр`}>
        <input type="hidden" name="otp" value={value} readOnly tabIndex={-1} aria-hidden="true" />
        <div className="auth-otp__cells">
          {cells.map((cell, index) => (
            <input
              key={index}
              ref={(element) => {
                inputRefs.current[index] = element;
              }}
              id={index === 0 ? "staff-otp-0" : undefined}
              className={`auth-otp__cell${invalid ? " auth-otp__cell--invalid" : ""}`}
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              autoComplete={index === 0 ? "one-time-code" : "off"}
              maxLength={1}
              value={cell}
              disabled={disabled}
              aria-label={`Цифра ${index + 1} кода из ${OTP_LENGTH}`}
              aria-invalid={invalid || undefined}
              onChange={(event) => handleChange(index, event.target.value)}
              onKeyDown={(event) => handleKeyDown(index, event)}
              onPaste={handlePaste}
              onFocus={(event) => event.currentTarget.select()}
            />
          ))}
        </div>
      </div>
    );
  },
);
