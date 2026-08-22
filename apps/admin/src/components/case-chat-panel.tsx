"use client";

import { labelAuthorKind } from "@/lib/ui-labels";
import { useEffect, useRef } from "react";

export type CaseChatMessage = {
  id: string;
  author_kind: string;
  body: string;
  created_at: string;
};

function bubbleClass(authorKind: string): string {
  if (authorKind === "client" || authorKind === "representative") {
    return "case-chat-bubble case-chat-bubble--client";
  }
  if (authorKind === "system") return "case-chat-bubble case-chat-bubble--system";
  return "case-chat-bubble case-chat-bubble--staff";
}

export function CaseChatPanel({
  messages,
  maxLinked,
  maxUserId,
  maxBusinessUrl,
  body,
  onBodyChange,
  busy,
  onSendMax,
  onSendInternal,
}: {
  messages: CaseChatMessage[];
  maxLinked: boolean;
  maxUserId: string | null;
  maxBusinessUrl: string | null;
  body: string;
  onBodyChange: (value: string) => void;
  busy: boolean;
  onSendMax: () => void;
  onSendInternal: () => void;
}) {
  const feedRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = feedRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages]);

  return (
    <aside className="case-chat panel" id="max-reply-panel" aria-label="Переписка с клиентом">
      <div className="case-chat-head">
        <h2>Чат с клиентом</h2>
        <p className="hint">
          {maxLinked
            ? "Лента дела. Отправка в MAX уходит в личный бот клиента."
            : "Лента дела. MAX не привязан — можно писать во внутреннюю переписку."}
        </p>
      </div>

      <div className="case-chat-feed" ref={feedRef}>
        {messages.length === 0 ? (
          <p className="hint case-chat-empty">Пока нет сообщений — история появится здесь.</p>
        ) : (
          <ul className="case-chat-list">
            {messages.map((m) => (
              <li key={m.id} className={bubbleClass(m.author_kind)}>
                <span className="meta">
                  {labelAuthorKind(m.author_kind)} ·{" "}
                  {new Date(m.created_at).toLocaleString("ru-RU", {
                    day: "2-digit",
                    month: "2-digit",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
                <p>{m.body}</p>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="case-chat-composer">
        <textarea
          id="max-reply-text"
          rows={3}
          value={body}
          onChange={(e) => onBodyChange(e.target.value)}
          placeholder={
            maxLinked
              ? "Сообщение клиенту (в MAX и в ленту дела)"
              : "Сообщение в ленту дела"
          }
          disabled={busy}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
              e.preventDefault();
              if (maxLinked) onSendMax();
              else onSendInternal();
            }
          }}
        />
        <div className="case-chat-actions">
          {maxLinked ? (
            <button
              type="button"
              className="max-action-btn max-action-btn--inline"
              disabled={busy || !body.trim()}
              onClick={onSendMax}
            >
              Отправить в MAX
            </button>
          ) : null}
          <button
            type="button"
            className={maxLinked ? "ghost" : undefined}
            disabled={busy || !body.trim()}
            onClick={onSendInternal}
          >
            {maxLinked ? "Только в ленту" : "Отправить"}
          </button>
        </div>
        <p className="hint">
          Ссылка max.ru/…_1_bot открывает ваш личный чат с ботом, не переписку клиента.
          {maxBusinessUrl && maxUserId
            ? ` В MAX Business → «Проверка стажа-личный бот» → Диалоги → user_id ${maxUserId}.`
            : ""}
        </p>
      </div>
    </aside>
  );
}
