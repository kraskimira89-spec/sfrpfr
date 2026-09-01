"use client";

import { FormEvent, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { BOT_TYPING_TIMEOUT_HINT } from "../../../../shared/bot-typing";
import { useBotTypingIndicator } from "@/lib/use-bot-typing-indicator";

type CaseMessage = {
  id: string;
  author_kind: string;
  body: string;
  created_at: string;
};

type ChatFilter = "all" | "staff" | "client" | "system";

function authorLabel(kind: string) {
  if (kind === "client") return "Вы";
  if (kind === "representative") return "Представитель";
  if (kind === "system") return "Бот MAX";
  if (kind === "staff" || kind === "expert" || kind === "operator") return "Специалист";
  return kind;
}

function bubbleClass(authorKind: string): string {
  if (authorKind === "client" || authorKind === "representative") {
    return "case-chat-bubble case-chat-bubble--client";
  }
  if (authorKind === "system") return "case-chat-bubble case-chat-bubble--bot";
  return "case-chat-bubble case-chat-bubble--staff";
}

function filterKind(authorKind: string, filter: ChatFilter): boolean {
  if (filter === "all") return true;
  if (filter === "staff") return authorKind === "staff" || authorKind === "expert" || authorKind === "operator";
  if (filter === "client") return authorKind === "client" || authorKind === "representative";
  return authorKind === "system";
}

function dayKey(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "unknown";
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function dayLabel(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const today = new Date();
  const yday = new Date();
  yday.setDate(today.getDate() - 1);
  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();
  if (sameDay(d, today)) return "Сегодня";
  if (sameDay(d, yday)) return "Вчера";
  return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "long", year: "numeric" });
}

function linkify(text: string): ReactNode[] {
  const parts = text.split(/(https?:\/\/[^\s]+)/g);
  return parts.map((part, i) =>
    /^https?:\/\//.test(part) ? (
      <a key={`u-${i}`} href={part} target="_blank" rel="noreferrer">
        {part}
      </a>
    ) : (
      <span key={`t-${i}`}>{part}</span>
    ),
  );
}

type FeedItem =
  | { type: "day"; key: string; label: string }
  | {
      type: "message";
      key: string;
      id: string;
      author_kind: string;
      body: string;
      created_at: string;
    };

function buildFeed(messages: CaseMessage[], filter: ChatFilter): FeedItem[] {
  const filtered = messages.filter((m) => filterKind(m.author_kind, filter));
  const out: FeedItem[] = [];
  let lastDay = "";
  for (const row of filtered) {
    const dk = dayKey(row.created_at);
    if (dk !== lastDay) {
      out.push({ type: "day", key: `day-${dk}`, label: dayLabel(row.created_at) });
      lastDay = dk;
    }
    out.push({
      type: "message",
      key: `msg-${row.id}`,
      id: row.id,
      author_kind: row.author_kind,
      body: row.body,
      created_at: row.created_at,
    });
  }
  return out;
}

export function ClientCaseChatPanel({
  messages,
  body,
  busy,
  onBodyChange,
  onSend,
}: {
  messages: CaseMessage[];
  body: string;
  busy: boolean;
  onBodyChange: (value: string) => void;
  onSend: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const [filter, setFilter] = useState<ChatFilter>("all");
  const feedRef = useRef<HTMLDivElement | null>(null);
  const feed = useMemo(() => buildFeed(messages, filter), [messages, filter]);
  const { showBotTyping, showBotTypingTimeout } = useBotTypingIndicator(messages);

  useEffect(() => {
    const el = feedRef.current;
    if (!el) return;
    requestAnimationFrame(() => {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    });
  }, [feed.length, showBotTyping, showBotTypingTimeout]);

  return (
    <aside className="case-chat panel client-chat-panel" aria-label="Чат по делу">
      <div className="case-chat-head">
        <h2>Чат по делу</h2>
        <p className="hint">История: ваши сообщения, ответы бота, ответы специалиста и загруженные документы.</p>
        <div className="case-chat-filters" role="group" aria-label="Фильтр сообщений">
          {(
            [
              ["all", "Все"],
              ["staff", "Специалист"],
              ["client", "Вы"],
              ["system", "Бот MAX"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={filter === id ? "case-chat-filter on" : "case-chat-filter"}
              onClick={() => setFilter(id)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="case-chat-feed" ref={feedRef}>
        {feed.length === 0 ? (
          <p className="hint case-chat-empty">Сообщений пока нет.</p>
        ) : (
          <ul className="case-chat-list">
            {feed.map((item) => {
              if (item.type === "day") {
                return (
                  <li key={item.key} className="case-chat-day">
                    {item.label}
                  </li>
                );
              }
              const isDocument = item.body.startsWith("[Документ] ");
              return (
                <li key={item.key} className={bubbleClass(item.author_kind)}>
                  <span className="meta">
                    {authorLabel(item.author_kind)} ·{" "}
                    {new Date(item.created_at).toLocaleString("ru-RU", {
                      day: "2-digit",
                      month: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                  {isDocument ? <p className="case-chat-doc">{linkify(item.body)}</p> : <p>{linkify(item.body)}</p>}
                </li>
              );
            })}
            {showBotTyping ? (
              <li className="case-chat-bubble case-chat-bubble--bot case-chat-typing" aria-live="polite">
                <span className="meta">Бот MAX · печатает…</span>
                <p className="case-chat-typing-dots" aria-hidden="true">
                  <span></span><span></span><span></span>
                </p>
              </li>
            ) : null}
            {showBotTypingTimeout ? (
              <li className="case-chat-bubble case-chat-bubble--bot" aria-live="polite">
                <span className="meta">Бот MAX</span>
                <p className="hint">{BOT_TYPING_TIMEOUT_HINT}</p>
              </li>
            ) : null}
          </ul>
        )}
      </div>

      <form className="case-chat-composer" onSubmit={onSend}>
        <label htmlFor="client-case-message">Ваше сообщение</label>
        <textarea
          id="client-case-message"
          rows={3}
          value={body}
          onChange={(event) => onBodyChange(event.target.value)}
          maxLength={4000}
          required
          disabled={busy}
          placeholder="Напишите вопрос специалисту"
        />
        <div className="case-chat-actions">
          <button type="submit" disabled={busy || !body.trim()}>
            Отправить
          </button>
        </div>
      </form>
    </aside>
  );
}
