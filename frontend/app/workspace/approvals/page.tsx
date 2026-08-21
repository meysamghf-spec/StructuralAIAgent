import { Suspense } from "react";
import ApprovalsWorkspaceClient from "./ApprovalsWorkspaceClient";

export default function ApprovalsWorkspacePage() {
  return (
    <Suspense fallback={<p className="muted">Loading approvals…</p>}>
      <ApprovalsWorkspaceClient />
    </Suspense>
  );
}
