import { ChatRunsSection } from "@/components/common/ChatRunsSection";
import { CHAT_ORIGIN_TITLE } from "@/lib/runs-titles";
import { Frame3dWorkspacePanel } from "@/components/frame3d/Frame3dWorkspacePanel";
import { LegacySection } from "@/components/frame3d/LegacySection";
import ResultsWorkspaceClient from "./ResultsWorkspaceClient";

export default function ResultsWorkspacePage() {
  return (
    <>
      {/* The frame analysis is shown once, in the frame section below (result or inline missing-inputs form);
          this list keeps the history of the other run types (AutoCAD drawings, beams, optimization, …). */}
      <ChatRunsSection title={CHAT_ORIGIN_TITLE} excludeKinds={["frame3d_analysis"]} />
      <Frame3dWorkspacePanel mode="results" />
      <LegacySection label="results">
        <ResultsWorkspaceClient />
      </LegacySection>
    </>
  );
}
