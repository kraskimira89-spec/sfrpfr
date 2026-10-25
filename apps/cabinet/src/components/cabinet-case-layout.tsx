"use client";

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";

const STORAGE_KEY = "cabinet-case-chat-width";
const MIN_CHAT = 300;
const MAX_CHAT = 720;
const DEFAULT_CHAT = 420;

export function clampChatWidth(px: number, viewportWidth: number): number {
  const maxByViewport = Math.max(MIN_CHAT, Math.floor(viewportWidth * 0.48));
  const upper = Math.min(MAX_CHAT, maxByViewport);
  return Math.min(upper, Math.max(MIN_CHAT, Math.round(px)));
}

function readStoredWidth(): number | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const n = Number(raw);
    if (!Number.isFinite(n)) return null;
    return clampChatWidth(n, window.innerWidth);
  } catch {
    return null;
  }
}

/**
 * Две колонки на широком экране: маршрут/этапы слева, чат справа.
 * Ширина чата адаптируется к viewport и вручную тянется разделителем.
 */
export function CabinetCaseLayout({
  main,
  chat,
}: {
  main: ReactNode;
  chat: ReactNode;
}) {
  const splitterId = useId();
  const layoutRef = useRef<HTMLDivElement | null>(null);
  const dragging = useRef(false);
  const [chatWidth, setChatWidth] = useState<number | null>(null);
  const [viewportWide, setViewportWide] = useState(false);

  useEffect(() => {
    const sync = () => {
      setViewportWide(window.innerWidth >= 960);
      setChatWidth((prev) => {
        if (prev == null) return readStoredWidth();
        return clampChatWidth(prev, window.innerWidth);
      });
    };
    sync();
    window.addEventListener("resize", sync);
    return () => window.removeEventListener("resize", sync);
  }, []);

  const persist = useCallback((px: number) => {
    try {
      localStorage.setItem(STORAGE_KEY, String(px));
    } catch {
      /* ignore */
    }
  }, []);

  const applyFromClientX = useCallback(
    (clientX: number) => {
      const el = layoutRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const next = clampChatWidth(rect.right - clientX, window.innerWidth);
      setChatWidth(next);
      persist(next);
    },
    [persist],
  );

  const onPointerDown = useCallback(
    (event: ReactPointerEvent<HTMLButtonElement>) => {
      if (!viewportWide) return;
      dragging.current = true;
      event.currentTarget.setPointerCapture(event.pointerId);
      applyFromClientX(event.clientX);
    },
    [applyFromClientX, viewportWide],
  );

  const onPointerMove = useCallback(
    (event: ReactPointerEvent<HTMLButtonElement>) => {
      if (!dragging.current) return;
      applyFromClientX(event.clientX);
    },
    [applyFromClientX],
  );

  const onPointerUp = useCallback((event: ReactPointerEvent<HTMLButtonElement>) => {
    dragging.current = false;
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      /* ignore */
    }
  }, []);

  const resetWidth = useCallback(() => {
    const next = clampChatWidth(DEFAULT_CHAT, window.innerWidth);
    setChatWidth(next);
    persist(next);
  }, [persist]);

  const style = {
    ...(chatWidth != null ? { ["--case-chat-width" as string]: `${chatWidth}px` } : {}),
  } as CSSProperties;

  return (
    <div
      ref={layoutRef}
      className="cabinet-case-layout cabinet-case-layout--resizable"
      style={style}
      data-layout={viewportWide ? "side-by-side" : "stacked"}
      data-chat-width={chatWidth ?? "auto"}
    >
      <div className="cabinet-case-main">{main}</div>
      <button
        type="button"
        id={splitterId}
        className="cabinet-case-splitter"
        aria-label="Изменить ширину чата"
        title="Тяните, чтобы изменить ширину чата. Двойной щелчок — сброс."
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onDoubleClick={resetWidth}
      />
      {chat}
    </div>
  );
}
