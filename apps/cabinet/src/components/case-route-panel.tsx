"use client";

import {
  chapterTitle,
  chaptersFromWork,
  currentChapterId,
  kitMarksFromWork,
  nextStepFromWork,
  recentEventsFromWork,
  requiredProgressLabel,
  type ClientWorkLike,
} from "@/lib/case-route";

type Props = {
  work: ClientWorkLike;
  caseNumber: string;
  busy?: boolean;
  expertAssigned?: boolean;
  warning: string;
  onPrimaryAction: () => void;
};

function chapterMark(state: string) {
  if (state === "done") return "✓";
  if (state === "current") return "●";
  return "○";
}

function kitSymbol(mark: string) {
  if (mark === "done") return "✓";
  if (mark === "checking") return "◷";
  if (mark === "fix") return "!";
  if (mark === "need") return "○";
  return "·";
}

export function CaseRoutePanel({
  work,
  caseNumber,
  busy,
  expertAssigned,
  warning,
  onPrimaryAction,
}: Props) {
  const chapters = chaptersFromWork(work);
  const chapterId = currentChapterId(work);
  const { heading, lead } = chapterTitle(chapterId);
  const step = nextStepFromWork(work);
  const kit = kitMarksFromWork(work);
  const events = recentEventsFromWork(work);
  const progress = requiredProgressLabel(work);

  return (
    <section className="case-route panel accent" aria-labelledby="case-route-title">
      <p className="case-route-kicker">Дело ПС-{caseNumber}</p>
      <h2 id="case-route-title" className="case-route-title">
        Мой маршрут
      </h2>

      <ol className="case-route-chapters" aria-label="Главы маршрута">
        {chapters.map((chapter) => (
          <li key={chapter.id} className={`case-route-chapter case-route-chapter--${chapter.state}`}>
            <span className="case-route-chapter-mark" aria-hidden>
              {chapterMark(chapter.state)}
            </span>
            <span className="case-route-chapter-label">
              {chapter.label}
              {chapter.state === "current" ? (
                <span className="case-route-here"> — вы здесь</span>
              ) : null}
            </span>
          </li>
        ))}
      </ol>

      <div className="case-route-chapter-body">
        <h3>{heading}</h3>
        <p>{lead}</p>
        {progress && chapterId === "documents" ? <p className="hint">{progress}</p> : null}
      </div>

      <div className="case-route-next" aria-live="polite">
        <h3>{step.mode === "waiting" ? "Сейчас действует специалист" : "Ваш следующий шаг"}</h3>
        <p className="case-route-next-title">
          <strong>{step.title}</strong>
        </p>
        <p>{step.why}</p>
        <div className="case-route-actions">
          {step.mode === "action" && step.primaryLabel ? (
            <button type="button" disabled={busy} onClick={onPrimaryAction}>
              {step.primaryLabel}
            </button>
          ) : null}
          {step.howtoUrl && step.howtoLabel ? (
            <a className="secondary" href={step.howtoUrl} target="_blank" rel="noreferrer">
              {step.howtoLabel}
            </a>
          ) : null}
          <a className="secondary" href="#case-chat-input">
            {step.mode === "waiting" ? "Задать вопрос" : "Нужна помощь"}
          </a>
          {step.mode === "action" ? (
            <a className="secondary" href="#case-chat-input">
              Не могу получить документ
            </a>
          ) : null}
        </div>
        <p className="hint">Можно продолжить позже — загруженные файлы сохраняются в деле.</p>
      </div>

      {kit.length > 0 ? (
        <div className="case-route-kit">
          <h3>Ваш комплект</h3>
          <ul className="case-route-kit-list">
            {kit.map((row) => (
              <li key={row.key} className={`case-route-kit-item case-route-kit-item--${row.mark}`}>
                <span className="case-route-kit-mark" aria-hidden>
                  {kitSymbol(row.mark)}
                </span>
                <div>
                  <strong>{row.title}</strong>
                  <p className="hint">
                    Статус: {row.statusText}
                    {row.purpose ? ` — ${row.purpose}` : ""}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="case-route-specialist">
        <h3>Ваш специалист</h3>
        {expertAssigned ? (
          <p>Специалист назначен. Пишите в чат по делу — ответ появится здесь и в MAX.</p>
        ) : (
          <p>Специалист ещё не назначен. Вопросы можно задать в чате — команда ответит.</p>
        )}
        <p className="case-route-actions">
          <a className="secondary" href="#case-chat-input">
            Написать в чат
          </a>
        </p>
      </div>

      <div className="case-route-events">
        <h3>Последние события</h3>
        {events.length === 0 ? (
          <p className="hint">Значимые события появятся здесь по мере работы с документами.</p>
        ) : (
          <ul className="case-route-events-list">
            {events.map((event) => (
              <li key={`${event.when}-${event.text}`}>
                <span className="case-route-event-when">{event.when}</span>
                <span>{event.text}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <p className="hint case-route-warning">{warning}</p>
    </section>
  );
}
