import { AutocadDrawingsSection } from "@/components/autocad/AutocadDrawingsSection";
import { CadDrawingsPanel } from "@/components/cad/CadDrawingsPanel";
import { LegacySection } from "@/components/frame3d/LegacySection";
import CadWorkspaceClient from "./CadWorkspaceClient";

export default function CadWorkspacePage() {
  return (
    <>
      <CadDrawingsPanel />
      <AutocadDrawingsSection />
      <LegacySection label="cad">
        <CadWorkspaceClient />
      </LegacySection>
    </>
  );
}
