import { Frame3dWorkspacePanel } from "@/components/frame3d/Frame3dWorkspacePanel";
import { LegacySection } from "@/components/frame3d/LegacySection";
import AnalysisWorkspaceClient from "./AnalysisWorkspaceClient";

export default function AnalysisWorkspacePage() {
  return (
    <>
      <Frame3dWorkspacePanel mode="analysis" />
      <LegacySection label="analysis">
        <AnalysisWorkspaceClient />
      </LegacySection>
    </>
  );
}
