"use client";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { FormEvent, useEffect, useState } from "react";
import {
  STAFF_AUTH_MESSAGES,
  STAFF_LOGIN_COPY,
  isValidEmailAddress,
  mapStaffAuthError,
  maskEmail,
  safeStaffAuthNotice,
} from "@/lib/auth-messages";

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
      <p className="eyebrow">
        <a className="brand-home-link" href={siteUrl} title="На главную" aria-label="На главную">
          <img
            className="brand-logo"
            src="/logo-light.png"
            width={40}
            height={40}
            alt="Проверка стажа"
          />
          Проверка стажа · сотрудники
        </a>
      </p>
    </>
  );
}

export function StaffAuthTrustPanel() {
  return (
    <aside className="auth-trust" aria-label={STAFF_LOGIN_COPY.trustTitle}>
      <h2>{STAFF_LOGIN_COPY.trustTitle}</h2>
      <ul>
        {STAFF_LOGIN_COPY.trustItems.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
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
    const resending = otpSent;
    setBusy(true);
    setNotice("");
    try {
      const { error } = await supabase.auth.signInWithOtp({
        email: email.trim().toLowerCase(),
        options: { shouldCreateUser: false },
      });
      if (error) throw error;
      setOtpSent(true);
      setAuthStep("otp");
      setOtpResendUntil(Date.now() + OTP_RESEND_MS);
      setNotice(resending ? STAFF_LOGIN_COPY.otpResent : STAFF_LOGIN_COPY.otpSentGeneric);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (/signups not allowed|user not found|unable to find/i.test(msg)) {
        setOtpSent(true);
        setAuthStep("otp");
        setOtpResendUntil(Date.now() + OTP_RESEND_MS);
        setNotice(resending ? STAFF_LOGIN_COPY.otpResent : STAFF_LOGIN_COPY.otpSentGeneric);
      } else {
        setNotice(mapStaffAuthError(err, STAFF_AUTH_MESSAGES.AUTH_DELIVERY_FAILED));
      }
    } finally {
      setBusy(false);
    }
  }

  async function verifyEmailOtp(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase) {
      setNotice(STAFF_AUTH_MESSAGES.AUTH_CONFIG_MISSING);
      return;
    }
    if (!otpCode.trim()) {
      setNotice(STAFF_AUTH_MESSAGES.AUTH_CODE_REQUIRED);
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      const { error } = await supabase.auth.verifyOtp({
        email: email.trim().toLowerCase(),
        token: otpCode.trim(),
        type: "email",
      });
      if (error) throw error;
    } catch (err) {
      const msg = err instanceof Error ? err.message.toLowerCase() : "";
      if (/expired/.test(msg)) {
        setNotice(STAFF_AUTH_MESSAGES.AUTH_CODE_EXPIRED);
      } else {
        setNotice(STAFF_AUTH_MESSAGES.AUTH_CODE_INVALID);
      }
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
          <StaffAuthTrustPanel />
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
              <h1>{STAFF_LOGIN_COPY.checkInboxTitle}</h1>
              <p className="lead lead-compact">
                {STAFF_LOGIN_COPY.checkInboxLead} {maskEmail(email)}. {STAFF_LOGIN_COPY.enterCode}
              </p>
              <form className="auth-form" onSubmit={verifyEmailOtp}>
                <label htmlFor="staff-otp">Код из письма</label>
                <input
                  id="staff-otp"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  autoFocus
                  maxLength={8}
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, "").slice(0, 8))}
                  required
                  disabled={busy}
                />
                <button type="submit" disabled={busy}>
                  {STAFF_LOGIN_COPY.signIn}
                </button>
              </form>
              <button
                type="button"
                className="ghost"
                disabled={busy || otpResendLeft > 0}
                onClick={() => void requestEmailOtp()}
              >
                {otpResendLeft > 0
                  ? `Отправить код ещё раз через ${otpResendLeft} сек.`
                  : "Отправить код ещё раз"}
              </button>
              <button type="button" className="linkish" onClick={goEmailStep}>
                {STAFF_LOGIN_COPY.changeEmail}
              </button>
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

          {notice && authStep !== "register_done" ? (
            <p className="notice" role="status" aria-live="polite">
              {safeStaffAuthNotice(notice)}
            </p>
          ) : null}
        </section>
        <StaffAuthTrustPanel />
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
        <StaffAuthTrustPanel />
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
