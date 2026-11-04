"use client";

import { usePathname } from "next/navigation";

import { ProjectSwitcher } from "@/components/project/ProjectSwitcher";
import { useUiLang } from "@/hooks/useUiLang";

// Sections that are account-wide (not tied to one project) get no project bar.
const ACCOUNT_SECTIONS = ["/workspace/admin", "/workspace/upgrades", "/workspace/agents"];

/** Compact "active project" selector at the top of every project section; switching reloads the section's inputs. */
export function WorkspaceProjectBar() {
  const pathname = usePathname() ?? "";
  const { t } = useUiLang();
  if (ACCOUNT_SECTIONS.some((p) => pathname.startsWith(p))) return null;
  return (
    <div className="workspace-project-bar" data-testid="workspace-project-bar">
      <span className="muted workspace-project-bar-label">{t("Inputs and results on this page are for project")}</span>
      <ProjectSwitcher variant="bar" />
    </div>
  );
}
