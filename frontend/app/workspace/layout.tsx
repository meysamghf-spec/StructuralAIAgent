import { WorkspaceProjectBar } from "@/components/project/WorkspaceProjectBar";

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <WorkspaceProjectBar />
      {children}
    </>
  );
}
