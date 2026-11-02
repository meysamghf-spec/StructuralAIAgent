import { Frame3dWorkspacePanel } from "@/components/frame3d/Frame3dWorkspacePanel";
import { LegacySection } from "@/components/frame3d/LegacySection";
import { ModelImportPanel } from "@/components/model-import/ModelImportPanel";
import ModelWorkspaceClient from "./ModelWorkspaceClient";

export default function ModelWorkspacePage() {
  return (
    <>
      <ModelImportPanel />
      <Frame3dWorkspacePanel mode="model" />
      <LegacySection label="model">
        <ModelWorkspaceClient />
      </LegacySection>
    </>
  );
}
