import { Suspense } from "react";
import { notFound } from "next/navigation";
import { RoutePreviewClient } from "./route-preview-client";

/**
 * Изолированный preview реального CaseWorkMap + чат справа.
 * В production-сборке скрыт (404), кроме явного ALLOW_ROUTE_PREVIEW=1.
 */
export default function RoutePreviewPage() {
  const allow =
    process.env.NODE_ENV !== "production" || process.env.ALLOW_ROUTE_PREVIEW === "1";
  if (!allow) {
    notFound();
  }
  return (
    <Suspense fallback={<p className="hint">Загрузка preview…</p>}>
      <RoutePreviewClient />
    </Suspense>
  );
}
