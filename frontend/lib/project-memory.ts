import { apiFetch } from "@/lib/api";

export type ProjectChatMemory = {
  project_id: string;
  text: string;
  stats: { conversations: number; messages: number; recent_verbatim: number; summarized: number; facts: number; chars: number };
};

export function getProjectChatMemory(projectId: string): Promise<ProjectChatMemory> {
  return apiFetch<ProjectChatMemory>(`/api/v1/conversations/project-memory/${encodeURIComponent(projectId)}`);
}

export function projectMemoryLabel(m: ProjectChatMemory | null, fa: boolean): string {
  const n = m?.stats.messages ?? 0;
  const c = m?.stats.conversations ?? 0;
  if (!m || n === 0) return fa ? "حافظه پروژه: هنوز خالی" : "Project memory: empty";
  return fa ? `حافظه پروژه: ${c} گفتگوی دیگر، ${n} پیام` : `Project memory: ${c} other chats, ${n} messages`;
}
