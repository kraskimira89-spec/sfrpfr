"use client";

import {
  addedDocumentsFromWork,
  chapterTitle,
  chaptersFromWork,
  currentChapterId,
  kitMarksFromWork,
  nextStepFromWork,
  requiredProgressLabel,
  resolveRoutePrimaryAction,
  type ClientWorkLike,
  type RoutePrimaryAction,
} from "@/lib/case-route";

type Props = {
  work: ClientWorkLike;
  caseNumber: string;
  busy?: boolean;
  expertAssigned?: boolean;
  warning: string;
  hasContractHandler?: boolean;
  onPrimaryAction: (action: Exclude<RoutePrimaryAction, { kind: "unavailable" } | { kind: "none" }>) => void;
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
  hasContractHandler,
  onPrimaryAction,
}: Props) {
  const chapters = chaptersFromWork(work);
  const chapterId = currentChapterId(work);
  const { heading, lead } = chapterTitle(chapterId);
  const step = nextStepFromWork(work);
  const kit = kitMarksFromWork(work);
  const addedDocs = addedDocumentsFromWork(work);
  const progress = requiredProgressLabel(work);
  const action = resolveRoutePrimaryAction(work, { hasContractHandler });
  const unavailable = action.kind === "unavailable" ? action.reason : null;
  const canRun =
    action.kind === "consent" ||
    action.kind === "contract" ||
    action.kind === "pay" ||
    action.kind === "upload" ||
    action.kind === "result";

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
        {step.consequenceHint ? <p className="hint case-route-consequence">{step.consequenceHint}</p> : null}
        {unavailable ? (
          <p className="hint doc-alert" role="status">
            {unavailable}
          </p>
        ) : null}
        <div className="case-route-actions">
          {step.mode === "action" && step.primaryLabel && canRun ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                if (
                  action.kind === "consent" ||
                  action.kind === "contract" ||
                  action.kind === "pay" ||
                  action.kind === "upload" ||
                  action.kind === "result"
                ) {
                  onPrimaryAction(action);
                }
              }}
            >
              {step.primaryLabel}
            </button>
          ) : null}
          {step.howtoUrl && step.howtoLabel ? (
            <a className="secondary" href={step.howtoUrl} target="_blank" rel="noreferrer">
              {step.howtoLabel}
            </a>
          ) : null}
          <a className="secondary" href="#case-chat-input">
            {step.helpLabel}
          </a>
          {step.showCantGetDocument ? (
            <a className="secondary" href="#case-chat-input">
              Не могу получить документ
            </a>
          ) : null}
        </div>
        {step.showContinueLaterHint ? (
          <p className="hint">Можно продолжить позже — загруженные файлы сохраняются в деле.</p>
        ) : null}
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
        <h3>Добавленные документы</h3>
        {addedDocs.length === 0 ? (
          <p className="hint">Здесь появятся документы после загрузки. Это не хронологическая лента событий.</p>
        ) : (
          <ul className="case-route-events-list">
            {addedDocs.map((event) => (
              <li key={`${event.when}-${event.text}`}>
                <span className="case-route-event-when">Загружено: {event.when}</span>
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
