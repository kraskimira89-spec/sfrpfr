import assert from "node:assert/strict";
import test from "node:test";
import {
  deriveFollowUpUiState,
  todayInControlTz,
} from "./follow-up-control.ts";

test("follow-up UI: need_assign without control date", () => {
  assert.equal(
    deriveFollowUpUiState({
      submissionConfirmed: true,
      followUpCompleted: false,
      responseReceived: false,
      controlAt: null,
    }),
    "need_assign",
  );
});

test("follow-up UI: overdue_internal is not SFR deadline", () => {
  const state = deriveFollowUpUiState({
    submissionConfirmed: true,
    followUpCompleted: false,
    responseReceived: false,
    controlAt: "2020-01-01T12:00:00+05:00",
  });
  assert.equal(state, "overdue_internal");
});

test("follow-up UI: today helper returns YYYY-MM-DD", () => {
  assert.match(todayInControlTz(), /^\d{4}-\d{2}-\d{2}$/);
});
