import { Suspense } from "react";
import ReportsWorkspaceClient from "./ReportsWorkspaceClient";

export default function ReportsWorkspacePage() {
  return (
    <Suspense fallback={<p className="muted">Loading reports…</p>}>
      <ReportsWorkspaceClient />
    </Suspense>
  );
}
