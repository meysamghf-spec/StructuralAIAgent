import { Frame3dWorkspacePanel } from "@/components/frame3d/Frame3dWorkspacePanel";
import { LegacySection } from "@/components/frame3d/LegacySection";
import ModelWorkspaceClient from "./ModelWorkspaceClient";

export default function ModelWorkspacePage() {
  return (
    <>
      <Frame3dWorkspacePanel mode="model" />
      <LegacySection label="model">
        <ModelWorkspaceClient />
      </LegacySection>
    </>
  );
}
