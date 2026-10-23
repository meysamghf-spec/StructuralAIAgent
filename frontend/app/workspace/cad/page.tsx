import { AutocadDrawingsSection } from "@/components/autocad/AutocadDrawingsSection";
import { StructuralSetSection } from "@/components/autocad/StructuralSetSection";
import { FrameDownloads } from "@/components/frame3d/FrameDownloads";
import { CadDrawingsPanel } from "@/components/cad/CadDrawingsPanel";
import { LegacySection } from "@/components/frame3d/LegacySection";
import CadWorkspaceClient from "./CadWorkspaceClient";

export default function CadWorkspacePage() {
  return (
    <>
      <StructuralSetSection />
      <FrameDownloads groups={["drawings", "models", "figures"]} title="Drawings & model downloads" />
      <AutocadDrawingsSection />
      <CadDrawingsPanel />
      <LegacySection label="cad">
        <CadWorkspaceClient />
      </LegacySection>
    </>
  );
}
