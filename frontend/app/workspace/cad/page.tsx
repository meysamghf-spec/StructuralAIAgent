import { AutocadDrawingsSection } from "@/components/autocad/AutocadDrawingsSection";
import { StructuralSetSection } from "@/components/autocad/StructuralSetSection";
import { CadDrawingsPanel } from "@/components/cad/CadDrawingsPanel";
import { LegacySection } from "@/components/frame3d/LegacySection";
import CadWorkspaceClient from "./CadWorkspaceClient";

export default function CadWorkspacePage() {
  return (
    <>
      <StructuralSetSection />
      <AutocadDrawingsSection />
      <CadDrawingsPanel />
      <LegacySection label="cad">
        <CadWorkspaceClient />
      </LegacySection>
    </>
  );
}
