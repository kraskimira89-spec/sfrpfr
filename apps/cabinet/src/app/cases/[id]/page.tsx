import { redirect } from "next/navigation";

type Props = {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

/**
 * Deep-link ТЗ-09: /cases/{id} → /?case={id}&…
 * ClientCabinet читает query (включая link_max / view / paid).
 */
export default async function CaseDeepLinkPage({ params, searchParams }: Props) {
  const { id } = await params;
  const query = await searchParams;
  const qs = new URLSearchParams();
  qs.set("case", id);
  for (const [key, value] of Object.entries(query)) {
    if (key === "case") continue;
    if (typeof value === "string") qs.set(key, value);
    else if (Array.isArray(value) && value[0]) qs.set(key, value[0]);
  }
  redirect(`/?${qs.toString()}`);
}
