import { Frame3dWorkspacePanel } from "@/components/frame3d/Frame3dWorkspacePanel";
import { LegacySection } from "@/components/frame3d/LegacySection";
import AnalysisLegacyClient from "./AnalysisLegacyClient";
import AnalysisWorkspaceClient from "./AnalysisWorkspaceClient";

// Full Analysis page: analysis results + «آنالیز» button, the 3D frame section, and the analysis-run list.
export default function AnalysisWorkspacePage() {
  return (
    <>
      <AnalysisWorkspaceClient />
      <Frame3dWorkspacePanel mode="analysis" />
      <LegacySection label="analysis">
        <AnalysisLegacyClient />
      </LegacySection>
    </>
  );
}
