"use client";

import { DownloadsPanel } from "@/components/frame3d/DownloadsPanel";
import { useLatestFrame3d } from "@/components/frame3d/Frame3dWorkspacePanel";
import type { DownloadGroup } from "@/lib/frame3d-downloads";

/** Downloads for the current project's latest frame run (used by section pages that don't hold the payload). */
export function FrameDownloads({ groups, title, collapsed, optimization }: { groups?: DownloadGroup[]; title?: string; collapsed?: boolean; optimization?: unknown }) {
  const { projectId, inputs } = useLatestFrame3d();
  return <DownloadsPanel inputs={inputs} projectId={projectId} groups={groups} title={title} collapsed={collapsed} optimization={optimization} />;
}

export default FrameDownloads;
