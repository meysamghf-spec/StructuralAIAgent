import { ChatRunsSection } from "@/components/common/ChatRunsSection";
import { FrameDownloads } from "@/components/frame3d/FrameDownloads";
import ValidationWorkspaceClient from "./ValidationWorkspaceClient";

export default function ValidationWorkspacePage() {
  return (
    <>
      <ChatRunsSection />
      <FrameDownloads groups={["analysis", "design", "reports"]} title="Validation tables (2800 / Mabhas 9 checks)" />
      <ValidationWorkspaceClient />
    </>
  );
}
