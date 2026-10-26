import assert from "node:assert/strict";
import test from "node:test";

import { parsePeriodsCsv, periodsToCsv } from "./periods-csv.ts";

test("periods csv roundtrip", () => {
  const csv = periodsToCsv(
    [{ period_id: "a", start: "2000-01-01", end: "2001-01-01", label: "завод" }],
    [{ period_id: "b", start: "2002", end: "2003", label: "север" }],
  );
  const { ils, labor } = parsePeriodsCsv(csv);
  assert.equal(ils.length, 1);
  assert.equal(labor.length, 1);
  assert.equal(ils[0]?.period_id, "a");
  assert.equal(labor[0]?.label, "север");
});
