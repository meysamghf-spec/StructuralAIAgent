import { ImportedModelCard } from "@/components/model-import/ImportedModelCard";
import { DesignRunPage } from "@/components/design/DesignRunPage";
import { Frame3dWorkspacePanel } from "@/components/frame3d/Frame3dWorkspacePanel";
import { LegacySection } from "@/components/frame3d/LegacySection";
import DesignLegacyClient from "./DesignLegacyClient";

// Full Design page: design results + «طراحی» button, the 3D frame section, and the design-run list.
export default function DesignWorkspacePage() {
  return (
    <>
      <DesignRunPage />
      <ImportedModelCard mode="design" />
      <Frame3dWorkspacePanel mode="design" />
      <LegacySection label="design">
        <DesignLegacyClient />
      </LegacySection>
    </>
  );
}
