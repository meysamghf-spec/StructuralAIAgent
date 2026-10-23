import { LegacySection } from "@/components/frame3d/LegacySection";
import { FrameDownloads } from "@/components/frame3d/FrameDownloads";
import { ReportPanel } from "@/components/frame3d/ReportPanel";
import ReportsWorkspaceClient from "./ReportsWorkspaceClient";

export default function ReportsWorkspacePage() {
  return (
    <>
      <ReportPanel />
      <FrameDownloads />
      <LegacySection label="reports">
        <ReportsWorkspaceClient />
      </LegacySection>
    </>
  );
}
