"use client";

import { labelAuthorKind } from "@/lib/ui-labels";
import { chatAwaitsStaff, situationBadges } from "@/lib/case-indicators";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BOT_TYPING_TIMEOUT_HINT } from "../../../../shared/bot-typing";
import { useBotTypingIndicator } from "@/lib/use-bot-typing-indicator";

export type CaseChatMessage = {
  id: string;
  author_kind: string;
  body: string;
  created_at: string;
};

type ChatFilter = "all" | "staff" | "client" | "system";

const BUTTONS_RE = /\n\n\[Кнопки бота: ([^\]]+)\]\s*$/;

function splitBody(body: string): { text: string; buttons: string[]; isDocument: boolean } {
  const isDocument = body.startsWith("[Документ] ");
  const match = body.match(BUTTONS_RE);
  if (!match) return { text: body, buttons: [], isDocument };
  return {
    text: body.slice(0, match.index).trimEnd(),
    buttons: match[1].split(" · ").map((x) => x.trim()).filter(Boolean),
    isDocument,
  };
}

function bubbleClass(authorKind: string): string {
  if (authorKind === "client" || authorKind === "representative") {
    return "case-chat-bubble case-chat-bubble--client";
  }
  if (authorKind === "system") return "case-chat-bubble case-chat-bubble--bot";
  return "case-chat-bubble case-chat-bubble--staff";
}

function authorLabel(authorKind: string): string {
  if (authorKind === "system") return "Бот MAX";
  return labelAuthorKind(authorKind);
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

function filterKind(authorKind: string, filter: ChatFilter): boolean {
  if (filter === "all") return true;
  if (filter === "staff") return authorKind === "staff";
  if (filter === "client") return authorKind === "client" || authorKind === "representative";
  return authorKind === "system";
}

type FeedItem =
  | { type: "day"; key: string; label: string }
  | {
      type: "group";
      key: string;
      author_kind: string;
      created_at: string;
      messages: CaseChatMessage[];
      collapsedExtra: number;
    };

function buildFeed(messages: CaseChatMessage[], filter: ChatFilter): FeedItem[] {
  const filtered = messages.filter((m) => filterKind(m.author_kind, filter));
  const out: FeedItem[] = [];
  let lastDay = "";
  let i = 0;
  while (i < filtered.length) {
    const m = filtered[i];
    const dk = dayKey(m.created_at);
    if (dk !== lastDay) {
      out.push({ type: "day", key: `day-${dk}`, label: dayLabel(m.created_at) });
      lastDay = dk;
    }
    const group: CaseChatMessage[] = [m];
    let j = i + 1;
    while (
      j < filtered.length &&
      filtered[j].author_kind === m.author_kind &&
      dayKey(filtered[j].created_at) === dk
    ) {
      group.push(filtered[j]);
      j += 1;
    }
    // Схлопнуть точные дубли подряд в группе
    const unique: CaseChatMessage[] = [];
    let collapsed = 0;
    for (const row of group) {
      const prev = unique[unique.length - 1];
      if (prev && prev.body.trim() === row.body.trim()) {
        collapsed += 1;
        continue;
      }
      unique.push(row);
    }
    out.push({
      type: "group",
      key: `g-${m.id}`,
      author_kind: m.author_kind,
      created_at: m.created_at,
      messages: unique,
      collapsedExtra: collapsed,
    });
    i = j;
  }
  return out;
}

export function CaseChatPanel({
  messages,
  clientName = null,
  caseLabel = null,
  maxLinked,
  maxUserId,
  maxBusinessUrl,
  body,
  onBodyChange,
  busy,
  onSendMax,
  onSendInternal,
  suggestions,
  onSuggest,
  composerHighlight = false,
  marketingConsentLabel = null,
  onRequestMarketingConsent,
  waitingOn = null,
}: {
  messages: CaseChatMessage[];
  /** ФИО клиента в шапке чата. */
  clientName?: string | null;
  /** Идентификатор дела вида ПС-000123. */
  caseLabel?: string | null;
  maxLinked: boolean;
  maxUserId: string | null;
  maxBusinessUrl: string | null;
  body: string;
  onBodyChange: (value: string) => void;
  busy: boolean;
  onSendMax: () => void;
  onSendInternal: () => void;
  suggestions: string[];
  onSuggest: () => void;
  composerHighlight?: boolean;
  /** Краткий статус marketing consent по MAX (не ПДн). */
  marketingConsentLabel?: string | null;
  onRequestMarketingConsent?: () => void;
  waitingOn?: string | null;
}) {
  const feedRef = useRef<HTMLDivElement | null>(null);
  /** Автоскролл вниз только если пользователь уже у низа ленты (иначе история «отскакивает»). */
  const stickToBottomRef = useRef(true);
  const [filter, setFilter] = useState<ChatFilter>("all");
  const [expandedDup, setExpandedDup] = useState<Record<string, boolean>>({});

  const feed = useMemo(() => buildFeed(messages, filter), [messages, filter]);

  const awaitsStaff = useMemo(
    () => chatAwaitsStaff(messages) || waitingOn === "staff",
    [messages, waitingOn],
  );
  const headBadges = useMemo(
    () =>
      situationBadges({
        waiting_on: waitingOn,
        chat_awaits_staff: awaitsStaff,
        max_linked: maxLinked,
      }).filter((b) => b.kind === "reply" || b.kind === "docs" || b.kind === "payment" || b.kind === "sfr"),
    [waitingOn, awaitsStaff, maxLinked],
  );

  const { showBotTyping, showBotTypingTimeout } = useBotTypingIndicator(messages);

  const lastMessageKey = useMemo(() => {
    const last = messages[messages.length - 1];
    return last ? `${last.id}:${last.created_at}:${messages.length}` : `0:${messages.length}`;
  }, [messages]);

  const isNearBottom = useCallback((el: HTMLElement, thresholdPx = 96) => {
    return el.scrollHeight - el.scrollTop - el.clientHeight <= thresholdPx;
  }, []);

  const scrollFeedToEnd = useCallback((behavior: ScrollBehavior = "smooth") => {
    const el = feedRef.current;
    if (!el) return;
    requestAnimationFrame(() => {
      el.scrollTo({ top: el.scrollHeight, behavior });
    });
  }, []);

  const onFeedScroll = useCallback(() => {
    const el = feedRef.current;
    if (!el) return;
    stickToBottomRef.current = isNearBottom(el);
  }, [isNearBottom]);

  // Смена фильтра — снова к низу.
  useEffect(() => {
    stickToBottomRef.current = true;
    scrollFeedToEnd("auto");
  }, [filter, scrollFeedToEnd]);

  // Новые сообщения / typing — только если пользователь у низа.
  // Своё сообщение сотрудника всегда показывает низ (после «Отправить в MAX»).
  useEffect(() => {
    const last = messages[messages.length - 1];
    if (last?.author_kind === "staff") {
      stickToBottomRef.current = true;
    }
    if (!stickToBottomRef.current) return;
    scrollFeedToEnd();
  }, [lastMessageKey, messages, showBotTyping, showBotTypingTimeout, scrollFeedToEnd]);

  return (
    <aside className="case-chat panel" id="max-reply-panel" aria-label="Переписка с клиентом">
      <div className="case-chat-head">
        <h2>Чат с клиентом</h2>
        <p className="case-chat-client-id" title="Клиент и номер дела">
          <strong>{(clientName || "").trim() || "Клиент без ФИО"}</strong>
          {caseLabel ? <span className="case-chat-case-no"> · {caseLabel}</span> : null}
        </p>
        {headBadges.length > 0 ? (
          <div className="situation-badges" style={{ marginBottom: 6 }}>
            {headBadges.map((b) => (
              <span key={b.id} className={`badge badge--${b.kind}`} title={b.title}>
                {b.label}
              </span>
            ))}
          </div>
        ) : null}
        {awaitsStaff ? (
          <p className="case-chat-await" role="status">
            Нужен ответ сотрудника
          </p>
        ) : null}
        <div className="case-chat-filters" role="group" aria-label="Фильтр сообщений">
          {(
            [
              ["all", "Все"],
              ["staff", "Сотрудник"],
              ["client", "Клиент"],
              ["system", "Система"],
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

      <div className="case-chat-feed" ref={feedRef} onScroll={onFeedScroll}>
        {feed.length === 0 ? (
          <p className="hint case-chat-empty">
            Пока пусто. Здесь появятся сообщения бота, нажатия клиента и ответы сотрудника.
          </p>
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
              const showAll = expandedDup[item.key];
              const visible = showAll
                ? item.messages
                : item.messages.length > 1 && item.collapsedExtra > 0
                  ? item.messages
                  : item.messages;
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
                  {visible.map((m) => {
                    const parsed = splitBody(m.body);
                    return (
                      <div key={m.id} className="case-chat-chunk">
                        {parsed.isDocument ? (
                          <p className="case-chat-doc">{parsed.text}</p>
                        ) : (
                          <p>{parsed.text}</p>
                        )}
                        {parsed.buttons.length > 0 ? (
                          <div className="case-chat-buttons" aria-label="Кнопки бота в MAX">
                            {parsed.buttons.map((label) => (
                              <span key={`${m.id}-${label}`} className="case-chat-btn-chip">
                                {label}
                              </span>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                  {item.collapsedExtra > 0 && !showAll ? (
                    <button
                      type="button"
                      className="linkish"
                      onClick={() => setExpandedDup((s) => ({ ...s, [item.key]: true }))}
                    >
                      Показать ещё {item.collapsedExtra}
                    </button>
                  ) : null}
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

      <div className={`case-chat-composer${composerHighlight ? " case-chat-composer--flash" : ""}`}>
        {suggestions.length > 0 ? (
          <div className="case-chat-buttons" aria-label="Варианты ответа DeepSeek">
            {suggestions.map((item) => (
              <button
                key={item}
                type="button"
                className="case-chat-btn-chip case-chat-btn-chip--clickable"
                onClick={() => onBodyChange(item)}
                title="Подставить этот вариант ответа в поле сообщения ниже"
              >
                {item.length > 80 ? `${item.slice(0, 80)}…` : item}
              </button>
            ))}
          </div>
        ) : null}
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
          title={
            maxLinked
              ? "Текст уйдёт клиенту в MAX и сохранится в ленте дела"
              : "Текст сохранится только в ленте дела"
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
          <button
            type="button"
            className="ghost"
            disabled={busy}
            onClick={onSuggest}
            title="DeepSeek предложит 2–3 варианта ответа по истории чата. Не отправляет само — только варианты для выбора"
          >
            Подсказать ответы (DeepSeek)
          </button>
          {maxLinked ? (
            <button
              type="button"
              className="max-action-btn max-action-btn--inline"
              disabled={busy || !body.trim()}
              onClick={onSendMax}
              title="Отправить текст клиенту в MAX и записать в ленту дела"
            >
              Отправить в MAX
            </button>
          ) : null}
          <button
            type="button"
            className={maxLinked ? "ghost" : undefined}
            disabled={busy || !body.trim()}
            onClick={onSendInternal}
            title={
              maxLinked
                ? "Сохранить сообщение только в ленте дела, без отправки в MAX"
                : "Сохранить сообщение в ленте дела"
            }
          >
            {maxLinked ? "Только в ленту" : "Отправить"}
          </button>
        </div>
        <p className="hint">
          Ctrl+Enter — отправить.
          {maxBusinessUrl && maxUserId
            ? ` MAX Business · user_id ${maxUserId}.`
            : ""}
        </p>
        {maxLinked ? (
          <div className="case-chat-marketing" style={{ marginTop: "0.75rem" }}>
            <p className="hint" style={{ marginBottom: "0.35rem" }}>
              Маркетинг MAX: {marketingConsentLabel || "нет данных / нет согласия"}. Не путать с
              согласием на ПДн. Promo-шаблоны (`marketing_*`) без согласия не уйдут.
            </p>
            {onRequestMarketingConsent ? (
              <button
                type="button"
                className="ghost"
                disabled={busy}
                onClick={onRequestMarketingConsent}
                title="Отправить в MAX кнопки «Да, согласен» / «Нет»"
              >
                Запросить согласие на рассылку в MAX
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </aside>
  );
}
