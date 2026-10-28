import { Frame3dWorkspacePanel } from "@/components/frame3d/Frame3dWorkspacePanel";
import DesignWorkspaceClient from "./DesignWorkspaceClient";

/**
 * Design page: Mabhas 9 member design of the latest 3D frame run (D/C, rebar, strong column / weak beam, detailing),
 * followed by the project-model (PEM) code design checks. Analysis tables live on Results, foundations on Foundation.
 */
export default function DesignWorkspacePage() {
  return (
    <>
      <Frame3dWorkspacePanel mode="design" />
      <DesignWorkspaceClient />
    </>
  );
}
