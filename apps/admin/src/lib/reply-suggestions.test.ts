import assert from "node:assert/strict";
import test from "node:test";

import { latestClientMessageId, withoutSentSuggestion } from "./reply-suggestions.ts";

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
