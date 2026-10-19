import { Frame3dWorkspacePanel } from "@/components/frame3d/Frame3dWorkspacePanel";
import { LegacySection } from "@/components/frame3d/LegacySection";
import DesignWorkspaceClient from "./DesignWorkspaceClient";

export default function DesignWorkspacePage() {
  return (
    <>
      <Frame3dWorkspacePanel mode="design" />
      <LegacySection label="design">
        <DesignWorkspaceClient />
      </LegacySection>
    </>
  );
}
