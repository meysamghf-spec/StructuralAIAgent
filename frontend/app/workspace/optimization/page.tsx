import { ChatRunsSection } from "@/components/common/ChatRunsSection";
import OptimizationWorkspaceClient from "./OptimizationWorkspaceClient";

export default function OptimizationWorkspacePage() {
  return (
    <>
      <ChatRunsSection kinds={["frame_optimization", "frame3d_analysis"]} />
      <OptimizationWorkspaceClient />
    </>
  );
}
