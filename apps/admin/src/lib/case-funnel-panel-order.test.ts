/**
 * Регрессия: тела StageShell в case-funnel-main.tsx идут строго по STAGE_IDS.
 * Порядок данных адаптера сам по себе UI не чинит.
 */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { STAGE_IDS } from "./case-funnel-types.ts";

const here = path.dirname(fileURLToPath(import.meta.url));
const mainPath = path.resolve(here, "../components/case-funnel-main.tsx");

test("отрисованные id=funnel-* совпадают с STAGE_IDS по порядку", () => {
  const src = fs.readFileSync(mainPath, "utf8");
  const ids = [...src.matchAll(/id="funnel-([a-z0-9_]+)"/g)].map((m) => m[1]);
  assert.deepEqual(
    ids,
    [...STAGE_IDS],
    `ожидали ${STAGE_IDS.join(" → ")}, получили ${ids.join(" → ")}`,
  );
});
