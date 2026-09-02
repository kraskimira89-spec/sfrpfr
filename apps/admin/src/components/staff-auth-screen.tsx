"use client";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { FormEvent, useEffect, useRef, useState } from "react";
import {
  STAFF_AUTH_MESSAGES,
  STAFF_LOGIN_COPY,
  isValidEmailAddress,
  mapStaffAuthError,
  maskEmail,
  safeStaffAuthNotice,
} from "@/lib/auth-messages";
import {
  formatResendCountdown,
  getOtpSubmitLabel,
  isOtpComplete,
  normalizeOtpDigits,
} from "@/lib/staff-otp";
import { StaffOtpInput, type StaffOtpInputHandle } from "@/components/staff-otp-input";

const IS_DEV = process.env.NODE_ENV === "development";
const OTP_RESEND_MS = 60_000;

type AuthStep = "email" | "otp" | "max" | "register" | "register_done";

function chatUrlOnly(url: string): string {
  try {
    const u = new URL(url);
    u.search = "";
    u.hash = "";
    return u.toString();
  } catch {
    return url;
  }
}

function BrandHeader({ siteUrl }: { siteUrl: string }) {
  return (
    <>
      <a className="auth-back-link" href={siteUrl}>
        {STAFF_LOGIN_COPY.backToSite}
      </a>
      <div className="auth-brand">
        <a
          className="auth-brand__logo-link"
          href={siteUrl}
          title="На главную"
          aria-label="На главную"
        >
          <img
            className="brand-logo"
            src="/logo-light.png"
            width={40}
            height={40}
            alt=""
          />
        </a>
        <div className="auth-brand__text">
          <p className="auth-brand__name">{STAFF_LOGIN_COPY.brandName}</p>
          <p className="auth-brand__context">{STAFF_LOGIN_COPY.brandContext}</p>
        </div>
      </div>
    </>
  );
}

function AuthStepper({ step, label }: { step: string; label: string }) {
  return (
    <div className="auth-stepper" aria-label={`${step}. ${label}`}>
      <span className="auth-step">{step}</span>
      <span className="auth-step__label">{label}</span>
    </div>
  );
}

type StaffAuthTrustPanelProps = {
  variant?: "default" | "otp";
  maxAvailable?: boolean;
  onMaxLogin?: () => void;
  onRequestAccess?: () => void;
};

export function StaffAuthTrustPanel({
  variant = "default",
  maxAvailable = true,
  onMaxLogin,
  onRequestAccess,
}: StaffAuthTrustPanelProps) {
  return (
    <aside className="auth-trust" aria-label={STAFF_LOGIN_COPY.trustTitle}>
      <h2>{STAFF_LOGIN_COPY.trustTitle}</h2>
      <ul className="auth-trust__list">
        {STAFF_LOGIN_COPY.trustItems.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      {variant === "otp" ? (
        <>
          <div className="auth-trust__divider" aria-hidden="true" />
          <h3 className="auth-trust__help-title">{STAFF_LOGIN_COPY.trustHelpTitle}</h3>
          <p className="auth-trust__help-lead">{STAFF_LOGIN_COPY.trustHelpLead}</p>
          {maxAvailable && onMaxLogin ? (
            <button type="button" className="auth-alt-btn auth-trust__max-btn" onClick={onMaxLogin}>
              {STAFF_LOGIN_COPY.maxCta}
            </button>
          ) : null}
          {onRequestAccess ? (
            <button type="button" className="linkish auth-trust__access-link" onClick={onRequestAccess}>
              {STAFF_LOGIN_COPY.accessRequestLink}
            </button>
          ) : null}
        </>
      ) : null}
    </aside>
  );
}

type StaffAuthScreenProps = {
  supabase: SupabaseClient | null;
  apiBase: string;
  defaultMaxBotUrl: string;
  siteUrl: string;
};

export function StaffAuthScreen({
  supabase,
  apiBase,
  defaultMaxBotUrl,
  siteUrl,
}: StaffAuthScreenProps) {
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [registerPhone, setRegisterPhone] = useState("");
  const [registerRole, setRegisterRole] = useState("operator");
  const [registerReason, setRegisterReason] = useState("");
  const [registerConsent, setRegisterConsent] = useState(false);
  const [authStep, setAuthStep] = useState<AuthStep>("email");
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [otpResendUntil, setOtpResendUntil] = useState(0);
  const [clockMs, setClockMs] = useState(() => Date.now());
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [otpError, setOtpError] = useState("");
  const [otpStatus, setOtpStatus] = useState("");
  const otpInputRef = useRef<StaffOtpInputHandle>(null);
  const [maxTicket, setMaxTicket] = useState("");
  const [maxPairCode, setMaxPairCode] = useState("");
  const [maxWaitStatus, setMaxWaitStatus] = useState("");
  const [maxBotUrl, setMaxBotUrl] = useState(defaultMaxBotUrl);

  const authReady = Boolean(supabase);

  useEffect(() => {
    if (!otpResendUntil) {
      return;
    }
    const timer = window.setInterval(() => setClockMs(Date.now()), 500);
    return () => window.clearInterval(timer);
  }, [otpResendUntil]);

  const otpResendLeft = otpResendUntil
    ? Math.max(0, Math.ceil((otpResendUntil - clockMs) / 1000))
    : 0;

  function resetMax() {
    setMaxTicket("");
    setMaxPairCode("");
    setMaxWaitStatus("");
  }

  function goEmailStep() {
    setAuthStep("email");
    setOtpSent(false);
    setOtpCode("");
    setOtpError("");
    setOtpStatus("");
    setNotice("");
    resetMax();
  }

  function goRegisterStep() {
    setAuthStep("register");
    setNotice("");
    resetMax();
  }

  async function requestEmailOtp(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (!email.trim()) {
      setNotice(STAFF_LOGIN_COPY.emailRequired);
      return;
    }
    if (!isValidEmailAddress(email)) {
      setNotice(STAFF_AUTH_MESSAGES.AUTH_INVALID_EMAIL);
      return;
    }
    if (!supabase) {
      setNotice(STAFF_AUTH_MESSAGES.AUTH_CONFIG_MISSING);
      return;
    }
    if (!apiBase) {
      setNotice(STAFF_AUTH_MESSAGES.AUTH_CONFIG_MISSING);
      return;
    }
    const resending = otpSent;
    setBusy(true);
    setNotice("");
    try {
      const precheck = await fetch(`${apiBase}/api/portal/auth/staff/email-otp/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      });
      const precheckBody = (await precheck.json().catch(() => ({}))) as {
        allowed?: boolean;
        message?: string;
      };
      if (!precheck.ok) {
        throw new Error(
          typeof precheckBody.message === "string" ? precheckBody.message : "staff_email_precheck_failed",
        );
      }
      if (!precheckBody.allowed) {
        setNotice(
          safeStaffAuthNotice(
            precheckBody.message || "",
            STAFF_AUTH_MESSAGES.AUTH_EMAIL_UNKNOWN,
          ),
        );
        return;
      }
      const { error } = await supabase.auth.signInWithOtp({
        email: email.trim().toLowerCase(),
        options: { shouldCreateUser: false },
      });
      if (error) throw error;
      setOtpSent(true);
      setAuthStep("otp");
      setOtpCode("");
      setOtpError("");
      setOtpResendUntil(Date.now() + OTP_RESEND_MS);
      setOtpStatus(resending ? STAFF_LOGIN_COPY.otpResent : "");
      setNotice("");
    } catch (err) {
      setNotice(mapStaffAuthError(err, STAFF_AUTH_MESSAGES.AUTH_DELIVERY_FAILED));
    } finally {
      setBusy(false);
    }
  }

  async function verifyEmailOtp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase) {
      setOtpError(STAFF_AUTH_MESSAGES.AUTH_CONFIG_MISSING);
      return;
    }
    const code = normalizeOtpDigits(otpCode);
    if (!isOtpComplete(code)) {
      setOtpError(STAFF_AUTH_MESSAGES.AUTH_CODE_REQUIRED);
      otpInputRef.current?.focusFirst();
      return;
    }
    setBusy(true);
    setOtpError("");
    setOtpStatus("");
    try {
      const { error } = await supabase.auth.verifyOtp({
        email: email.trim().toLowerCase(),
        token: code,
        type: "email",
      });
      if (error) throw error;
      setOtpStatus(STAFF_LOGIN_COPY.otpSubmitSuccess);
    } catch (err) {
      const msg = err instanceof Error ? err.message.toLowerCase() : "";
      if (/expired/.test(msg)) {
        setOtpError(STAFF_AUTH_MESSAGES.AUTH_CODE_EXPIRED);
      } else {
        setOtpError(STAFF_AUTH_MESSAGES.AUTH_CODE_INVALID);
      }
      setOtpCode("");
      otpInputRef.current?.focusFirst();
    } finally {
      setBusy(false);
    }
  }

  async function requestMaxLogin() {
    if (!email.trim() || !isValidEmailAddress(email)) {
      setNotice(STAFF_LOGIN_COPY.emailRequired);
      return;
    }
    if (!apiBase) {
      setNotice(STAFF_AUTH_MESSAGES.AUTH_CONFIG_MISSING);
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const response = await fetch(`${apiBase}/api/portal/auth/otp/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ audience: "staff", email: email.trim().toLowerCase() }),
      });
      const body = (await response.json().catch(() => ({}))) as {
        detail?: string;
        ticket?: string;
        pair_code?: string;
        max_bot_url?: string;
        status?: string;
      };
      if (!response.ok) {
        throw new Error(typeof body.detail === "string" ? body.detail : "max_auth_failed");
      }
      setMaxTicket(body.ticket || "");
      setMaxPairCode(body.pair_code || "");
      setMaxWaitStatus(body.status || "pending_confirm");
      if (body.max_bot_url) setMaxBotUrl(body.max_bot_url);
      setAuthStep("max");
      setNotice("");
    } catch (err) {
      setNotice(mapStaffAuthError(err, STAFF_AUTH_MESSAGES.AUTH_DELIVERY_FAILED));
    } finally {
      setBusy(false);
    }
  }

  function openMaxChat() {
    window.open(chatUrlOnly(maxBotUrl), "_blank", "noopener,noreferrer");
  }

  useEffect(() => {
    if (!supabase || !apiBase || !maxTicket || authStep !== "max") return;
    let cancelled = false;
    const timer = window.setInterval(() => {
      void (async () => {
        try {
          const response = await fetch(
            `${apiBase}/api/portal/auth/otp/poll?ticket=${encodeURIComponent(maxTicket)}`,
          );
          const body = (await response.json().catch(() => ({}))) as {
            status?: string;
            token_hash?: string;
            type?: "email" | "sms";
            message?: string;
          };
          if (cancelled) return;
          if (body.status) setMaxWaitStatus(body.status);
          if (body.status === "approved" && body.token_hash) {
            const { error } = await supabase.auth.verifyOtp({
              token_hash: body.token_hash,
              type: body.type || "email",
            });
            if (error) throw error;
            resetMax();
            setNotice("");
          }
          if (body.status === "expired") {
            setNotice(STAFF_AUTH_MESSAGES.AUTH_CODE_EXPIRED);
          }
        } catch {
          if (!cancelled) {
            setNotice(mapStaffAuthError(null, STAFF_AUTH_MESSAGES.AUTH_UNKNOWN));
          }
        }
      })();
    }, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [supabase, apiBase, maxTicket, authStep]);

  async function submitAccessRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!registerConsent) {
      setNotice("Отметьте согласие с правилами работы с персональными данными клиентов.");
      return;
    }
    if (!fullName.trim()) {
      setNotice("Укажите фамилию и имя.");
      return;
    }
    if (!email.trim() || !isValidEmailAddress(email)) {
      setNotice(STAFF_AUTH_MESSAGES.AUTH_INVALID_EMAIL);
      return;
    }
    if (!apiBase) {
      setNotice(STAFF_AUTH_MESSAGES.AUTH_CONFIG_MISSING);
      return;
    }
    const roleLabels: Record<string, string> = {
      operator: "Специалист",
      admin: "Администратор",
      expert: "Руководитель",
      other: "Другое",
    };
    const roleLabel = roleLabels[registerRole] || registerRole;
    const displayName = [
      fullName.trim(),
      registerPhone.trim() ? `тел. ${registerPhone.trim()}` : "",
      `${roleLabel}`,
      registerReason.trim(),
    ]
      .filter(Boolean)
      .join(" · ");

    setBusy(true);
    setNotice("");
    try {
      const response = await fetch(`${apiBase}/api/public/staff-register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          display_name: displayName,
          consent: true,
        }),
      });
      const body = (await response.json().catch(() => ({}))) as {
        detail?: string;
        message?: string;
      };
      if (!response.ok) {
        const detail = typeof body.detail === "string" ? body.detail : "";
        if (response.status === 409 && /рассмотрении/i.test(detail)) {
          setAuthStep("register_done");
          setNotice(STAFF_LOGIN_COPY.registerPending);
          return;
        }
        if (response.status === 409) {
          setAuthStep("register_done");
          setNotice(STAFF_LOGIN_COPY.registerDone);
          return;
        }
        throw new Error(detail || "register_failed");
      }
      setAuthStep("register_done");
      setNotice(body.message || STAFF_LOGIN_COPY.registerDone);
    } catch (err) {
      setNotice(mapStaffAuthError(err, STAFF_AUTH_MESSAGES.AUTH_UNKNOWN));
    } finally {
      setBusy(false);
    }
  }

  const otpComplete = isOtpComplete(otpCode);
  const otpSubmitLabel = getOtpSubmitLabel({ busy, complete: otpComplete });
  const trustVariant = authStep === "otp" ? "otp" : "default";
  const maxAvailable = Boolean(apiBase);

  if (!authReady && !IS_DEV) {
    return (
      <main className="auth-layout auth-layout--split">
        <div className="auth-split">
          <section className="card auth-card">
            <BrandHeader siteUrl={siteUrl} />
            <h1>{STAFF_LOGIN_COPY.title}</h1>
            <p className="lead lead-compact" role="status" aria-live="polite">
              {STAFF_AUTH_MESSAGES.AUTH_CONFIG_MISSING}
            </p>
            {apiBase ? (
              <button type="button" className="auth-alt-btn" onClick={() => void requestMaxLogin()}>
                {STAFF_LOGIN_COPY.maxCta}
              </button>
            ) : null}
            <p className="hint">
              <a href={siteUrl}>{STAFF_LOGIN_COPY.backToSite}</a>
            </p>
          </section>
          <StaffAuthTrustPanel variant="default" maxAvailable={maxAvailable} />
        </div>
      </main>
    );
  }

  return (
    <main className="auth-layout auth-layout--split">
      <div className="auth-split">
        <section className="card auth-card">
          <BrandHeader siteUrl={siteUrl} />

          {authStep === "email" ? (
            <>
              <AuthStepper
                step={STAFF_LOGIN_COPY.stepEmail}
                label={STAFF_LOGIN_COPY.stepEmailLabel}
              />
              <h1>{STAFF_LOGIN_COPY.title}</h1>
              <p className="lead lead-compact">{STAFF_LOGIN_COPY.subtitle}</p>
              {IS_DEV && !authReady ? (
                <p className="auth-dev-diag">
                  DEV: задайте NEXT_PUBLIC_SUPABASE_URL и NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY в
                  apps/admin/.env.local
                </p>
              ) : null}
              <form className="auth-form" onSubmit={requestEmailOtp}>
                <label htmlFor="staff-email">{STAFF_LOGIN_COPY.emailLabel}</label>
                <input
                  id="staff-email"
                  type="email"
                  inputMode="email"
                  autoComplete="email"
                  placeholder={STAFF_LOGIN_COPY.emailPlaceholder}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  disabled={busy}
                />
                <button type="submit" disabled={busy || !authReady}>
                  {STAFF_LOGIN_COPY.getCode}
                </button>
              </form>
              <p className="hint">{STAFF_LOGIN_COPY.otpSentGeneric}</p>
              <div className="auth-or-divider" aria-hidden="true">
                {STAFF_LOGIN_COPY.orDivider}
              </div>
              <div className="auth-max-alt">
                <p className="auth-max-alt__title">{STAFF_LOGIN_COPY.maxTeaserTitle}</p>
                <p className="hint">{STAFF_LOGIN_COPY.maxTeaserLead}</p>
                <button
                  type="button"
                  className="auth-alt-btn"
                  disabled={busy}
                  onClick={() => void requestMaxLogin()}
                >
                  {STAFF_LOGIN_COPY.maxCta}
                </button>
              </div>
              <p className="hint">
                <button type="button" className="linkish" onClick={goRegisterStep}>
                  {STAFF_LOGIN_COPY.accessRequestLink}
                </button>
              </p>
            </>
          ) : null}

          {authStep === "otp" ? (
            <>
              <AuthStepper step={STAFF_LOGIN_COPY.stepOtp} label={STAFF_LOGIN_COPY.stepOtpLabel} />
              <h1>{STAFF_LOGIN_COPY.checkInboxTitle}</h1>
              <p className="lead lead-compact auth-otp-lead">
                {STAFF_LOGIN_COPY.checkInboxLead}{" "}
                <strong className="auth-otp-email">{maskEmail(email)}</strong>.{" "}
                {STAFF_LOGIN_COPY.enterCode}
              </p>
              <p id="otp-help" className="auth-otp-help">
                {STAFF_LOGIN_COPY.otpTtlHint}
              </p>
              <form className="auth-form auth-form--otp" onSubmit={verifyEmailOtp}>
                <StaffOtpInput
                  ref={otpInputRef}
                  value={otpCode}
                  onChange={(value) => {
                    setOtpCode(value);
                    if (otpError) setOtpError("");
                  }}
                  disabled={busy}
                  invalid={Boolean(otpError)}
                  autoFocus
                />
                <p id="otp-status" className="auth-otp-status" role="status" aria-live="polite">
                  {otpStatus}
                </p>
                {otpError ? (
                  <p className="auth-otp-error" role="alert" aria-live="assertive">
                    <span className="auth-otp-error__icon" aria-hidden="true">
                      !
                    </span>
                    {otpError}
                  </p>
                ) : null}
                <button
                  type="submit"
                  className={busy ? "auth-submit auth-submit--busy" : "auth-submit"}
                  disabled={busy || !otpComplete}
                  aria-describedby="otp-help otp-status"
                >
                  {otpSubmitLabel}
                </button>
              </form>
              <div className="auth-actions-row">
                <div className="auth-actions-row__item">
                  <p className="auth-actions-row__prompt">{STAFF_LOGIN_COPY.otpResendPrompt}</p>
                  <button
                    type="button"
                    className="linkish"
                    disabled={busy || otpResendLeft > 0}
                    onClick={() => void requestEmailOtp()}
                  >
                    {otpResendLeft > 0
                      ? `${STAFF_LOGIN_COPY.otpResendWait} ${formatResendCountdown(otpResendLeft)}`
                      : STAFF_LOGIN_COPY.otpResendAction}
                  </button>
                </div>
                <div className="auth-actions-row__item">
                  <p className="auth-actions-row__prompt">{STAFF_LOGIN_COPY.otpChangeEmailPrompt}</p>
                  <button type="button" className="linkish" disabled={busy} onClick={goEmailStep}>
                    {STAFF_LOGIN_COPY.changeEmail}
                  </button>
                </div>
              </div>
              <div className="auth-help-fallback">
                <p className="auth-help-fallback__title">{STAFF_LOGIN_COPY.otpHelpTitle}</p>
                <div className="auth-help-fallback__actions">
                  {maxAvailable ? (
                    <button
                      type="button"
                      className="linkish"
                      disabled={busy}
                      onClick={() => void requestMaxLogin()}
                    >
                      {STAFF_LOGIN_COPY.maxCta}
                    </button>
                  ) : null}
                  <button type="button" className="linkish" disabled={busy} onClick={goRegisterStep}>
                    {STAFF_LOGIN_COPY.accessRequestLink}
                  </button>
                </div>
              </div>
            </>
          ) : null}

          {authStep === "max" ? (
            <>
              <h1>{STAFF_LOGIN_COPY.maxTitle}</h1>
              <p className="lead lead-compact">{STAFF_LOGIN_COPY.maxLead}</p>
              <p className="max-wizard-status" role="status" aria-live="polite">
                {maxWaitStatus === "pending_manager"
                  ? "Ожидаем подтверждение руководителя в MAX…"
                  : STAFF_LOGIN_COPY.maxWaiting}
              </p>
              {maxPairCode ? (
                <p className="hint">
                  Код для ops-бота: <strong>{maxPairCode}</strong>
                </p>
              ) : null}
              <button type="button" className="max-action-btn" onClick={openMaxChat}>
                {STAFF_LOGIN_COPY.maxOpen}
              </button>
              <button type="button" className="linkish" onClick={goEmailStep}>
                {STAFF_LOGIN_COPY.maxEmailFallback}
              </button>
              <button type="button" className="ghost" onClick={goEmailStep}>
                {STAFF_LOGIN_COPY.maxCancel}
              </button>
            </>
          ) : null}

          {authStep === "register" ? (
            <>
              <h1>{STAFF_LOGIN_COPY.registerTitle}</h1>
              <p className="lead lead-compact">{STAFF_LOGIN_COPY.registerLead}</p>
              <form className="auth-form" onSubmit={submitAccessRequest}>
                <label htmlFor="reg-name">Фамилия, имя</label>
                <input
                  id="reg-name"
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  autoComplete="name"
                  required
                  disabled={busy}
                />
                <label htmlFor="reg-email">Рабочая почта</label>
                <input
                  id="reg-email"
                  type="email"
                  inputMode="email"
                  autoComplete="email"
                  placeholder={STAFF_LOGIN_COPY.emailPlaceholder}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  disabled={busy}
                />
                <label htmlFor="reg-phone">Телефон для связи — необязательно</label>
                <input
                  id="reg-phone"
                  type="tel"
                  inputMode="tel"
                  autoComplete="tel"
                  value={registerPhone}
                  onChange={(e) => setRegisterPhone(e.target.value)}
                  disabled={busy}
                />
                <label htmlFor="reg-role">Должность / роль</label>
                <select
                  id="reg-role"
                  value={registerRole}
                  onChange={(e) => setRegisterRole(e.target.value)}
                  disabled={busy}
                >
                  <option value="operator">Специалист</option>
                  <option value="admin">Администратор</option>
                  <option value="expert">Руководитель</option>
                  <option value="other">Другое</option>
                </select>
                <label htmlFor="reg-reason">Причина доступа / подразделение</label>
                <textarea
                  id="reg-reason"
                  rows={3}
                  value={registerReason}
                  onChange={(e) => setRegisterReason(e.target.value)}
                  required
                  disabled={busy}
                />
                <label className="auth-consent" htmlFor="reg-consent">
                  <input
                    id="reg-consent"
                    type="checkbox"
                    checked={registerConsent}
                    onChange={(e) => setRegisterConsent(e.target.checked)}
                    required
                  />
                  <span>
                    Согласен с правилами работы с персональными данными клиентов и{" "}
                    <a href={`${siteUrl}/soglasie/`} target="_blank" rel="noopener noreferrer">
                      политикой обработки ПДн
                    </a>
                  </span>
                </label>
                <button type="submit" disabled={busy || !registerConsent}>
                  {STAFF_LOGIN_COPY.registerSubmit}
                </button>
              </form>
              <p className="hint">
                <button type="button" className="linkish" onClick={goEmailStep}>
                  {STAFF_LOGIN_COPY.backToLogin}
                </button>
              </p>
            </>
          ) : null}

          {authStep === "register_done" ? (
            <>
              <h1>{STAFF_LOGIN_COPY.registerTitle}</h1>
              <p className="notice" role="status" aria-live="polite">
                {notice || STAFF_LOGIN_COPY.registerDone}
              </p>
              <button type="button" className="linkish" onClick={goEmailStep}>
                {STAFF_LOGIN_COPY.backToLogin}
              </button>
            </>
          ) : null}

          {notice && authStep !== "register_done" && authStep !== "otp" ? (
            <p className="notice" role="status" aria-live="polite">
              {safeStaffAuthNotice(notice)}
            </p>
          ) : null}
        </section>
        <StaffAuthTrustPanel
          variant={trustVariant}
          maxAvailable={maxAvailable}
          onMaxLogin={maxAvailable ? () => void requestMaxLogin() : undefined}
          onRequestAccess={goRegisterStep}
        />
      </div>
    </main>
  );
}

type StaffAccessGateProps = {
  supabase: SupabaseClient | null;
  siteUrl: string;
  blocked?: boolean;
  onRequestAccess: () => void;
};

export function StaffAccessGate({
  supabase,
  siteUrl,
  blocked = false,
  onRequestAccess,
}: StaffAccessGateProps) {
  return (
    <main className="auth-layout auth-layout--split">
      <div className="auth-split">
        <section className="card auth-card">
          <BrandHeader siteUrl={siteUrl} />
          <h1>
            {blocked ? STAFF_LOGIN_COPY.accessBlockedTitle : STAFF_LOGIN_COPY.accessPendingTitle}
          </h1>
          <p className="lead lead-compact">
            {blocked ? STAFF_LOGIN_COPY.accessBlockedLead : STAFF_LOGIN_COPY.accessPendingLead}
          </p>
          {!blocked ? (
            <button type="button" className="max-action-btn" onClick={onRequestAccess}>
              {STAFF_LOGIN_COPY.accessRequestCta}
            </button>
          ) : null}
          <button type="button" className="ghost" onClick={() => void supabase?.auth.signOut()}>
            {STAFF_LOGIN_COPY.signOut}
          </button>
          {!blocked ? (
            <button type="button" className="linkish" onClick={() => void supabase?.auth.signOut()}>
              {STAFF_LOGIN_COPY.backToLogin}
            </button>
          ) : null}
        </section>
        <StaffAuthTrustPanel variant="default" />
      </div>
    </main>
  );
}

export function createStaffSupabaseClient(): SupabaseClient | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
  const key =
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ??
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ??
    "";
  if (!url || !key) return null;
  return createClient(url, key);
}
