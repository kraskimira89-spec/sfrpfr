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

export function ClientCabinet() {
  const supabase = useMemo(
    () => (supabaseUrl && supabaseKey ? createClient(supabaseUrl, supabaseKey) : null),
    [],
  );
  const [session, setSession] = useState<Session | null>(null);
  const [email, setEmail] = useState("");
  const [notice, setNotice] = useState("");
  const [cases, setCases] = useState<CaseSummary[]>([]);

  useEffect(() => {
    if (!supabase) return;
    void supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
    });
    return () => data.subscription.unsubscribe();
  }, [supabase]);

  useEffect(() => {
    if (!session || !apiBase) return;
    void fetch(`${apiBase}/api/portal/me/cases`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
    })
      .then(async (response) => (response.ok ? response.json() : Promise.reject(response)))
      .then(setCases)
      .catch(() => setNotice("Не удалось загрузить дела. Повторите попытку позже."));
  }, [session]);

  async function requestMagicLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase) {
      setNotice("Кабинет ещё не настроен: нет public ключа Supabase.");
      return;
    }
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: window.location.origin },
    });
    setNotice(error ? "Не удалось отправить код. Проверьте адрес и попробуйте снова." : "Письмо с кодом отправлено.");
  }

  if (!session) {
    return (
      <main className="auth-layout">
        <section className="card">
          <p className="eyebrow">SFRFR</p>
          <h1>Кабинет клиента</h1>
          <p>Войдите по одноразовому коду, чтобы видеть только свои дела и документы.</p>
          <form onSubmit={requestMagicLink}>
            <label htmlFor="email">Email</label>
            <input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
            <button type="submit">Получить код</button>
          </form>
          {notice && <p className="notice">{notice}</p>}
        </section>
      </main>
    );
  }

  return (
    <main className="app-layout">
      <header>
        <div><strong>SFRFR</strong><span>Кабинет клиента</span></div>
        <button onClick={() => void supabase?.auth.signOut()}>Выйти</button>
      </header>
      <section className="warning">
        Решение по заявлению принимает СФР. Результат проверки и перерасчёт не гарантированы.
      </section>
      <section>
        <h1>Мои дела</h1>
        {cases.length === 0 ? (
          <p>Дел пока нет. Начните обращение через MAX или публичный сайт.</p>
        ) : (
          <ul className="case-list">
            {cases.map((caseItem) => (
              <li key={caseItem.id}>
                <strong>Дело {caseItem.id.slice(0, 8)}</strong>
                <span>Этап: {caseItem.pipeline_status}</span>
                <span>Открытых пунктов: {caseItem.checklist_open_count}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
      {notice && <p className="notice">{notice}</p>}
    </main>
  );
}
