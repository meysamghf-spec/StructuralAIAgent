import { ChatRunsSection } from "@/components/common/ChatRunsSection";
import { Frame3dWorkspacePanel } from "@/components/frame3d/Frame3dWorkspacePanel";

export default function FoundationWorkspacePage() {
  return (
    <>
      <Frame3dWorkspacePanel mode="foundation" />
      <ChatRunsSection kinds={["frame3d_analysis"]} />
    </>
  );
}
