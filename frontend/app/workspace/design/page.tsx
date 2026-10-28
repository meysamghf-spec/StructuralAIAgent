import { DesignRunPage } from "@/components/design/DesignRunPage";

/**
 * Design page: only the design results of the project and one "Design" button that runs the Mabhas 9 member design
 * (plus isolated footings) on the saved, analysed 3D frame model and shows the new results here.
 * Analysis tables live on Analysis/Results, drawings and downloads on their own pages.
 */
export default function DesignWorkspacePage() {
  return <DesignRunPage />;
}
