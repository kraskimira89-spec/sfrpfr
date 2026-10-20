import assert from "node:assert/strict";
import test from "node:test";

import {
  latestClientMessageId,
  latestSuggestionTriggerId,
  withoutSentSuggestion,
} from "./reply-suggestions.ts";

test("sent suggestion leaves the list", () => {
  const left = withoutSentSuggestion(
    ["Пришлите трудовую", "Напишите телефон"],
    "Пришлите трудовую",
  );
  assert.deepEqual(left, ["Напишите телефон"]);
});

test("edited text does not drop a different suggestion", () => {
  const left = withoutSentSuggestion(["Пришлите трудовую"], "Пришлите ИЛС");
  assert.deepEqual(left, ["Пришлите трудовую"]);
});

test("latest client message id follows the thread", () => {
  assert.equal(
    latestClientMessageId([
      { id: "1", author_kind: "client" },
      { id: "2", author_kind: "staff" },
      { id: "3", author_kind: "client" },
    ]),
    "3",
  );
  assert.equal(latestClientMessageId([]), null);
});

test("suggestion trigger reacts to document and type confirmation", () => {
  const base = [
    { id: "1", author_kind: "client", body: "Здравствуйте" },
    { id: "2", author_kind: "staff", body: "Пришлите выписку" },
  ];
  assert.equal(latestSuggestionTriggerId(base), "1");
  assert.equal(
    latestSuggestionTriggerId([
      ...base,
      { id: "3", author_kind: "system", body: "[Документ] ils.pdf · Выписка ИЛС" },
    ]),
    "3",
  );
  assert.equal(
    latestSuggestionTriggerId([
      ...base,
      {
        id: "4",
        author_kind: "system",
        body: "[Документ] ils.pdf · Клиент подтвердил: Выписка ИЛС",
      },
    ]),
    "4",
  );
  // Обычные системные сообщения бота триггером не являются.
  assert.equal(
    latestSuggestionTriggerId([
      ...base,
      { id: "5", author_kind: "system", body: "Файл получили — спасибо!" },
    ]),
    "1",
  );
  assert.equal(latestSuggestionTriggerId([]), null);
});
