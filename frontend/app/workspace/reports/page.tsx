import { LegacySection } from "@/components/frame3d/LegacySection";
import { ReportPanel } from "@/components/frame3d/ReportPanel";
import ReportsWorkspaceClient from "./ReportsWorkspaceClient";

export default function ReportsWorkspacePage() {
  return (
    <>
      <ReportPanel />
      <LegacySection label="reports">
        <ReportsWorkspaceClient />
      </LegacySection>
    </>
  );
}
