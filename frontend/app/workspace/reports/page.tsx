import { LegacySection } from "@/components/frame3d/LegacySection";
import { FrameDownloads } from "@/components/frame3d/FrameDownloads";
import { ReportPanel } from "@/components/frame3d/ReportPanel";
import { ReportsList } from "@/components/reports/ReportsList";
import ReportsWorkspaceClient from "./ReportsWorkspaceClient";

// Full Reports page: report list, calculation report panel, frame downloads, and the report-generation section.
export default function ReportsWorkspacePage() {
  return (
    <>
      <ReportsList />
      <ReportPanel />
      <FrameDownloads />
      <LegacySection label="reports">
        <ReportsWorkspaceClient />
      </LegacySection>
    </>
  );
}
