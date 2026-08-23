"use client";

import { useEffect, useMemo, useState } from "react";
import {
  BOT_TYPING_TIMEOUT_MS,
  awaitingBotReplyKey,
  isAwaitingBotReply,
  type BotTypingMessage,
} from "../../../../shared/bot-typing";

export function useBotTypingIndicator(messages: BotTypingMessage[]) {
  const awaiting = useMemo(() => isAwaitingBotReply(messages), [messages]);
  const replyKey = useMemo(() => awaitingBotReplyKey(messages), [messages]);
  const [timedOutKey, setTimedOutKey] = useState<string | null>(null);

  useEffect(() => {
    if (!replyKey) return;
    const timer = window.setTimeout(() => setTimedOutKey(replyKey), BOT_TYPING_TIMEOUT_MS);
    return () => window.clearTimeout(timer);
  }, [replyKey]);

  const timedOut = replyKey !== null && timedOutKey === replyKey;

  return {
    showBotTyping: awaiting && !timedOut,
    showBotTypingTimeout: awaiting && timedOut,
  };
}
