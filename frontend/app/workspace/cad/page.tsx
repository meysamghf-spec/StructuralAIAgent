import { CadDrawingsPanel } from "@/components/cad/CadDrawingsPanel";
import { LegacySection } from "@/components/frame3d/LegacySection";
import CadWorkspaceClient from "./CadWorkspaceClient";

export default function CadWorkspacePage() {
  return (
    <>
      <CadDrawingsPanel />
      <LegacySection label="cad">
        <CadWorkspaceClient />
      </LegacySection>
    </>
  );
}
