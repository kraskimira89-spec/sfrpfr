"use client";

import { createClient, type Session } from "@supabase/supabase-js";
import { FormEvent, useEffect, useMemo, useState } from "react";

type CaseSummary = {
  id: string;
  pipeline_status: string;
  b2c_status: string;
  checklist_open_count: number;
};

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "";

export function AdminCabinet() {
  const supabase = useMemo(
    () => (supabaseUrl && supabaseKey ? createClient(supabaseUrl, supabaseKey) : null),
    [],
  );
  const [session, setSession] = useState<Session | null>(null);
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [cases, setCases] = useState<CaseSummary[]>([]);

  useEffect(() => {
    if (!supabase) return;
    void supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => setSession(nextSession));
    return () => data.subscription.unsubscribe();
  }, [supabase]);

  useEffect(() => {
    if (!session || !apiBase) return;
    void fetch(`${apiBase}/api/portal/me/cases`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
    })
      .then(async (response) => (response.ok ? response.json() : Promise.reject(response)))
      .then(setCases)
      .catch(() => setMessage("Нет доступа: требуется роль оператора, эксперта или администратора."));
  }, [session]);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase) {
      setMessage("Кабинет ещё не настроен: нет public ключа Supabase.");
      return;
    }
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: window.location.origin },
    });
    setMessage(error ? "Не удалось отправить код." : "Письмо с кодом отправлено.");
  }

  if (!session) {
    return (
      <main className="auth-layout">
        <section className="card">
          <p className="eyebrow">SFRFR / INTERNAL</p>
          <h1>Кабинет сотрудника</h1>
          <form onSubmit={signIn}>
            <label htmlFor="email">Рабочий email</label>
            <input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
            <button type="submit">Получить код</button>
          </form>
          {message && <p className="notice">{message}</p>}
        </section>
      </main>
    );
  }

  return (
    <main className="app-layout">
      <header>
        <div><strong>SFRFR</strong><span>Кабинет сотрудника</span></div>
        <button onClick={() => void supabase?.auth.signOut()}>Выйти</button>
      </header>
      <section className="metrics">
        <article><span>Дел в доступе</span><strong>{cases.length}</strong></article>
        <article><span>Ожидают действий</span><strong>{cases.filter((item) => item.checklist_open_count > 0).length}</strong></article>
      </section>
      <section>
        <h1>Реестр дел</h1>
        <p className="hint">Набор полей и действий определяется серверной ролью.</p>
        <ul className="case-list">
          {cases.map((caseItem) => (
            <li key={caseItem.id}>
              <strong>Дело {caseItem.id.slice(0, 8)}</strong>
              <span>{caseItem.pipeline_status} · {caseItem.b2c_status}</span>
              <span>Открытых пунктов: {caseItem.checklist_open_count}</span>
            </li>
          ))}
        </ul>
      </section>
      {message && <p className="notice">{message}</p>}
    </main>
  );
}
