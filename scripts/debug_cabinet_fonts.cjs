/**
 * Debug instrumentation: подтверждает, что layout не импортирует next/font/google.
 * Пишет NDJSON в debug-a3952d.log (session a3952d).
 */
const fs = require("node:fs");
const path = require("node:path");

const app = process.argv[2] || "cabinet";
const root = path.resolve(__dirname, "..");
const layoutPath = path.join(root, "apps", app, "src", "app", "layout.tsx");
const logPath = path.join(root, "debug-a3952d.log");
const src = fs.readFileSync(layoutPath, "utf8");
const usesGoogle = /from\s+["']next\/font\/google["']/.test(src);
const usesFontsource = /@fontsource\/manrope/.test(src);

const entry = {
  sessionId: "a3952d",
  runId: process.env.DEBUG_RUN_ID || "post-fix",
  hypothesisId: "A",
  location: `scripts/debug_cabinet_fonts.cjs:${app}`,
  message: "font import mode check",
  data: {
    app,
    usesGoogleNextFont: usesGoogle,
    usesFontsource: usesFontsource,
    ok: !usesGoogle && usesFontsource,
  },
  timestamp: Date.now(),
};
fs.appendFileSync(logPath, `${JSON.stringify(entry)}\n`);
if (usesGoogle) {
  console.error(`[debug-fonts] ${app}: still imports next/font/google`);
  process.exit(1);
}
console.log(`[debug-fonts] ${app}: fontsource self-host ok`);
