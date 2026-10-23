import { ChatRunsSection } from "@/components/common/ChatRunsSection";
import TraceabilityWorkspaceClient from "./TraceabilityWorkspaceClient";

export default function TraceabilityWorkspacePage() {
  return (
    <>
      <ChatRunsSection />
      <TraceabilityWorkspaceClient />
    </>
  );
}
