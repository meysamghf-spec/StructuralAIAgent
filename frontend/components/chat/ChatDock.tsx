"use client";

import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

import { ChatComposer } from "@/components/chat/ChatComposer";
import { ChatThread } from "@/components/chat/ChatThread";
import { useAuth } from "@/hooks/useAuth";
import { useChat } from "@/hooks/useChat";
import { useProjectScope } from "@/hooks/useProjectScope";
import { useUiLang } from "@/hooks/useUiLang";

const OPEN_KEY = "saia.chatDock.open";
const WIDTH_KEY = "saia.chatDock.width";
const MOBILE_QUERY = "(max-width: 960px)";
export const CHAT_DOCK_MIN_W = 320;
export const CHAT_DOCK_MAX_W = 820;
const DEFAULT_W = 420;

export function clampDockWidth(w: number, viewport = typeof window !== "undefined" ? window.innerWidth : 1440): number {
  const max = Math.max(CHAT_DOCK_MIN_W, Math.min(CHAT_DOCK_MAX_W, viewport - 520));
  return Math.round(Math.min(max, Math.max(CHAT_DOCK_MIN_W, w)));
}

function readStored(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}
function writeStored(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

/**
 * Global project chat on every app page (Model, Analysis, Design, Detailing, Optimizer, Report...).
 * Desktop: docked, resizable side panel, open by default; the page content shrinks to make room.
 * Mobile: bottom sheet toggled by the floating Chat button.
 * The panel stays mounted while hidden, so the conversation, draft and results survive page navigation.
 */
export function ChatDock() {
  const [isMobile, setIsMobile] = useState(false);
  const [open, setOpenState] = useState(false);
  const [width, setWidth] = useState(DEFAULT_W);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia(MOBILE_QUERY);
    const mobile = mq.matches;
    setIsMobile(mobile);
    const stored = readStored(OPEN_KEY);
    // Desktop: open unless the user closed it. Mobile: closed unless the user left it open.
    setOpenState(stored === null ? !mobile : stored === "1");
    const w = Number(readStored(WIDTH_KEY));
    if (Number.isFinite(w) && w > 0) setWidth(clampDockWidth(w));
    setReady(true);
    const onChange = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const setOpen = useCallback((v: boolean) => {
    setOpenState(v);
    writeStored(OPEN_KEY, v ? "1" : "0");
  }, []);

  // Docked layout: reserve space on the shell so page content is never hidden behind the panel.
  useEffect(() => {
    const shell = document.querySelector<HTMLElement>(".shell");
    if (!shell) return;
    const docked = ready && open && !isMobile;
    shell.dataset.chatDocked = docked ? "true" : "false";
    shell.style.setProperty("--chat-dock-w", `${width}px`);
    return () => {
      shell.dataset.chatDocked = "false";
    };
  }, [ready, open, isMobile, width]);

  const startResize = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      e.preventDefault();
      const startX = e.clientX;
      const startW = width;
      let last = startW;
      const move = (ev: PointerEvent) => {
        last = clampDockWidth(startW + (startX - ev.clientX));
        setWidth(last);
      };
      const up = () => {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
        document.body.classList.remove("chat-dock-resizing");
        writeStored(WIDTH_KEY, String(last));
      };
      document.body.classList.add("chat-dock-resizing");
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
    },
    [width],
  );

  if (!ready) return null;
  return (
    <>
      {!open ? <DockToggle onClick={() => setOpen(true)} /> : null}
      <DockPanel
        open={open}
        mobile={isMobile}
        width={width}
        onClose={() => setOpen(false)}
        onResizeStart={startResize}
        onResizeKey={(delta) => {
          const w = clampDockWidth(width + delta);
          setWidth(w);
          writeStored(WIDTH_KEY, String(w));
        }}
      />
    </>
  );
}

function DockToggle({ onClick }: { onClick: () => void }) {
  const { t } = useUiLang();
  return (
    <button type="button" className="chat-dock-toggle" onClick={onClick} aria-label={t("Open chat")}>
      💬 {t("Chat")}
    </button>
  );
}

function DockPanel({
  open,
  mobile,
  width,
  onClose,
  onResizeStart,
  onResizeKey,
}: {
  open: boolean;
  mobile: boolean;
  width: number;
  onClose: () => void;
  onResizeStart: (e: ReactPointerEvent<HTMLDivElement>) => void;
  onResizeKey: (delta: number) => void;
}) {
  const { t, lang } = useUiLang();
  const { isAuthenticated, loading: authLoading } = useAuth();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const { projects, selectedProjectId, setSelectedProjectId, selectedProject, loading: projectsLoading } = useProjectScope();
  // projectsReady: never load history before the active project is known (no cross-project leakage).
  const chat = useChat({ isAuthenticated, authLoading, selectedProjectId, setSelectedProjectId, projectsReady: !projectsLoading });
  return (
    <aside
      className={mobile ? "chat-dock chat-dock--sheet" : "chat-dock chat-dock--docked"}
      data-open={open ? "true" : "false"}
      data-testid="chat-dock"
      hidden={!open}
      style={mobile ? undefined : { width }}
      aria-label={t("Project chat")}
      dir={lang === "fa" ? "rtl" : "ltr"}
    >
      {!mobile ? (
        <div
          className="chat-dock-resizer"
          role="separator"
          aria-orientation="vertical"
          aria-label={t("Resize chat")}
          tabIndex={0}
          onPointerDown={onResizeStart}
          onKeyDown={(e) => {
            if (e.key === "ArrowLeft") onResizeKey(24);
            if (e.key === "ArrowRight") onResizeKey(-24);
          }}
          data-testid="chat-dock-resizer"
        />
      ) : (
        <div className="chat-dock-grabber" aria-hidden="true" />
      )}
      <header className="chat-dock-header">
        <strong>{t("Project chat")}</strong>
        <select
          value={selectedProjectId ?? ""}
          onChange={(e) => setSelectedProjectId(e.target.value)}
          aria-label={t("Project")}
        >
          {projects.length === 0 ? <option value="">{t("No project selected")}</option> : null}
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <button type="button" className="button secondary" onClick={onClose} aria-label={t("Close chat")}>
          ✕
        </button>
      </header>
      {chat.error ? <div className="alert error">{chat.error}</div> : null}
      <div className="chat-dock-body">
        <ChatThread
          messages={chat.messages}
          busy={chat.busy}
          loadingMessages={chat.loadingMessages}
          executionPhase={chat.executionPhase}
          statusLabel={chat.statusLabel}
          projectId={selectedProjectId || null}
          projectName={selectedProject?.name ?? null}
          onApprovalResolved={() => void chat.handleApprovalResolved()}
        />
      </div>
      <ChatComposer
        variant="default"
        content={chat.content}
        attachments={chat.pendingAttachments}
        busy={chat.busy}
        projectSelected={Boolean(selectedProjectId)}
        mode={chat.mode}
        inputRef={inputRef}
        onContentChange={chat.setContent}
        onModeChange={chat.setMode}
        onSend={() => void chat.handleSend()}
        onPickFiles={(files: FileList | File[]) => void chat.handlePickFiles(files)}
        onRemoveAttachment={chat.removeAttachment}
      />
    </aside>
  );
}
