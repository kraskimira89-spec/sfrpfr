import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  draftTimeoutMessage,
  isAbortLikeError,
  reconcileDraftAfterClientFailure,
} from "./full-analysis-ui";

describe("full-analysis-ui", () => {
  it("reconcile: подставляет новую draft-версию после обрыва ответа", () => {
    const out = reconcileDraftAfterClientFailure({
      beforeId: "v1",
      after: {
        id: "v2",
        n: 2,
        status: "draft",
        markdown: "# Разбор\n\nПериод 1989–1997.",
      },
    });
    assert.equal(out.recovered, true);
    assert.match(out.markdown, /1989/);
    assert.match(out.notice, /на сервере/);
  });

  it("reconcile: не подставляет ту же версию", () => {
    const out = reconcileDraftAfterClientFailure({
      beforeId: "v1",
      after: { id: "v1", status: "remarks", markdown: "старое" },
    });
    assert.equal(out.recovered, false);
  });

  it("isAbortLikeError распознаёт AbortError и timeout-текст", () => {
    assert.equal(isAbortLikeError(new DOMException("aborted", "AbortError")), true);
    assert.equal(isAbortLikeError(new Error("Превышено время ожидания ИИ")), true);
    assert.equal(isAbortLikeError(new Error("network down")), false);
  });

  it("draftTimeoutMessage содержит секунды", () => {
    assert.match(draftTimeoutMessage(180_000), /180/);
  });
});
