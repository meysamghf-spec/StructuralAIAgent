import { Suspense } from "react";
import CadWorkspaceClient from "./CadWorkspaceClient";

export default function CadWorkspacePage() {
  return (
    <Suspense fallback={<p className="muted">Loading CAD workspace…</p>}>
      <CadWorkspaceClient />
    </Suspense>
  );
}
