"use client";

import { useEffect, useState } from "react";
import {
  BOT_TYPING_SLOW_MS,
  BOT_TYPING_TIMEOUT_MS,
  botTypingHint,
  lastClientAwaitAgeMs,
  type BotTypingMessage,
} from "../../../../shared/bot-typing";

export function useBotTypingIndicator(messages: BotTypingMessage[]) {
  const [, setTick] = useState(0);
  const ageMs = lastClientAwaitAgeMs(messages);
  const awaiting = ageMs !== null && ageMs < BOT_TYPING_TIMEOUT_MS;

  useEffect(() => {
    if (!awaiting) return undefined;
    const id = window.setInterval(() => setTick((n) => n + 1), 500);
    return () => window.clearInterval(id);
  }, [awaiting]);

  const slow = ageMs !== null && ageMs >= BOT_TYPING_SLOW_MS && ageMs < BOT_TYPING_TIMEOUT_MS;

  return {
    showBotTyping: ageMs !== null && ageMs < BOT_TYPING_SLOW_MS,
    showBotTypingTimeout: slow,
    botTypingHint: botTypingHint(ageMs),
  };
}
