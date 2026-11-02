import { ChatRunsSection } from "@/components/common/ChatRunsSection";
import { Frame3dWorkspacePanel } from "@/components/frame3d/Frame3dWorkspacePanel";
import { LegacySection } from "@/components/frame3d/LegacySection";
import ResultsWorkspaceClient from "./ResultsWorkspaceClient";

export default function ResultsWorkspacePage() {
  return (
    <>
      <ChatRunsSection />
      <Frame3dWorkspacePanel mode="results" />
      <LegacySection label="results">
        <ResultsWorkspaceClient />
      </LegacySection>
    </>
  );
}
