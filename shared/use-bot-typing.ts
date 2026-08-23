"use client";

import { useEffect, useMemo, useState } from "react";
import {
  BOT_TYPING_TIMEOUT_MS,
  awaitingBotReplyKey,
  isAwaitingBotReply,
  type BotTypingMessage,
} from "./bot-typing";

export function useBotTypingIndicator(messages: BotTypingMessage[]) {
  const awaiting = useMemo(() => isAwaitingBotReply(messages), [messages]);
  const replyKey = useMemo(() => awaitingBotReplyKey(messages), [messages]);
  const [timedOut, setTimedOut] = useState(false);

  useEffect(() => {
    if (!replyKey) {
      setTimedOut(false);
      return;
    }
    setTimedOut(false);
    const timer = window.setTimeout(() => setTimedOut(true), BOT_TYPING_TIMEOUT_MS);
    return () => window.clearTimeout(timer);
  }, [replyKey]);

  return {
    showBotTyping: awaiting && !timedOut,
    showBotTypingTimeout: awaiting && timedOut,
  };
}
