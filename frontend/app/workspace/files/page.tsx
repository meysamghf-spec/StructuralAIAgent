import { ChatRunsSection } from "@/components/common/ChatRunsSection";
import FilesWorkspaceClient from "./FilesWorkspaceClient";

export default function FilesWorkspacePage() {
  return (
    <>
      <ChatRunsSection kinds={["autocad", "frame3d_analysis"]} />
      <FilesWorkspaceClient />
    </>
  );
}
