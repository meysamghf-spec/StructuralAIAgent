import { Suspense } from "react";

import AssistantPageClient from "./AssistantPageClient";

export default async function AssistantPage({ params }: { params: Promise<{ type: string }> }) {
  const { type } = await params;
  return (
    <Suspense fallback={<p className="muted">…</p>}>
      <AssistantPageClient slug={type} />
    </Suspense>
  );
}
