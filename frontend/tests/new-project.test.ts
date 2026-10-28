import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearStoredActiveConversations,
  getStoredActiveConversationId,
  storeActiveConversationId,
} from "@/lib/chat";
import { listConversations } from "@/lib/chat-api";
import { getCurrentProjectId, setCurrentProjectId } from "@/lib/current-project";
import { PROJECT_NAME_MAX, PROJECTS_EVENT, cleanProjectName, createProjectAndSwitch } from "@/lib/project-actions";
import { UI_FA } from "@/lib/ui-i18n";

type FakeWindow = {
  localStorage: Storage;
  location: { href: string; search: string };
  history: { state: unknown; replaceState: (s: unknown, t: string, url: string) => void };
  dispatchEvent: (e: Event) => boolean;
  addEventListener: () => void;
  removeEventListener: () => void;
};

function installWindow(url: string): { events: Event[]; win: FakeWindow } {
  const store = new Map<string, string>();
  const events: Event[] = [];
  const localStorage = {
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
    key: (i: number) => [...store.keys()][i] ?? null,
    get length() {
      return store.size;
    },
  } as unknown as Storage;
  // Object.keys(localStorage) must list stored keys, like a real Storage.
  const proxied = new Proxy(localStorage, {
    ownKeys: () => [...store.keys()],
    getOwnPropertyDescriptor: (_t, key) =>
      typeof key === "string" && store.has(key)
        ? { enumerable: true, configurable: true, value: store.get(key) }
        : undefined,
  });
  const win: FakeWindow = {
    localStorage: proxied,
    location: { href: url, search: new URL(url).search },
    history: {
      state: null,
      replaceState: (_s, _t, next) => {
        const u = new URL(next, url);
        win.location.href = u.toString();
        win.location.search = u.search;
      },
    },
    dispatchEvent: (e) => {
      events.push(e);
      return true;
    },
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  };
  vi.stubGlobal("window", win);
  return { events, win };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("cleanProjectName", () => {
  it("trims, collapses whitespace and caps length", () => {
    expect(cleanProjectName("  Arak   office \n building ")).toBe("Arak office building");
    expect(cleanProjectName("   ")).toBe("");
    expect(cleanProjectName("x".repeat(500))).toHaveLength(PROJECT_NAME_MAX);
  });
});

describe("createProjectAndSwitch", () => {
  beforeEach(() => {
    installWindow("http://localhost/?project=old-project");
  });

  it("rejects an empty name without calling the API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(createProjectAndSwitch("   ")).rejects.toThrow();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("creates through /api/v1/projects, announces it and makes it the active project", async () => {
    const { events } = installWindow("http://localhost/?project=old-project");
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      expect(JSON.parse(String(init?.body))).toEqual({ name: "Tower B" });
      return new Response(JSON.stringify({ project: { id: "new-id", name: "Tower B" } }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const project = await createProjectAndSwitch("  Tower   B ");
    expect(project.id).toBe("new-id");
    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/v1/projects");
    expect(events.map((e) => e.type)).toEqual([PROJECTS_EVENT, "sa:current-project"]);
    expect(getCurrentProjectId()).toBe("new-id");
  });
});

describe("setCurrentProjectId", () => {
  it("rewrites a stale ?project= so the old project cannot win", () => {
    const { win } = installWindow("http://localhost/chat?project=old&x=1#h");
    setCurrentProjectId("new");
    expect(win.location.href).toBe("http://localhost/chat?project=new&x=1#h");
    expect(getCurrentProjectId()).toBe("new");
  });

  it("strips ?project= when the project is cleared", () => {
    installWindow("http://localhost/?project=old");
    setCurrentProjectId(null);
    expect(getCurrentProjectId()).toBeNull();
  });

  it("leaves URLs without ?project= alone", () => {
    const { win } = installWindow("http://localhost/reports");
    setCurrentProjectId("p1");
    expect(win.location.href).toBe("http://localhost/reports");
    expect(getCurrentProjectId()).toBe("p1");
  });
});

describe("per-project active conversation", () => {
  it("remembers a separate conversation per project and forgets all on sign-out", () => {
    installWindow("http://localhost/");
    storeActiveConversationId("c-a", "A");
    storeActiveConversationId("c-b", "B");
    storeActiveConversationId("c-none", null);
    expect(getStoredActiveConversationId("A")).toBe("c-a");
    expect(getStoredActiveConversationId("B")).toBe("c-b");
    expect(getStoredActiveConversationId(null)).toBe("c-none");
    storeActiveConversationId(null, "A");
    expect(getStoredActiveConversationId("A")).toBeNull();
    expect(getStoredActiveConversationId("B")).toBe("c-b");
    clearStoredActiveConversations();
    expect(getStoredActiveConversationId("B")).toBeNull();
    expect(getStoredActiveConversationId(null)).toBeNull();
  });
});

describe("listConversations scope", () => {
  function mockFetch() {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ conversations: [] }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }
  it("sends project_id / unassigned only when asked", async () => {
    installWindow("http://localhost/");
    const fetchMock = mockFetch();
    await listConversations();
    await listConversations({ project_id: "p 1" });
    await listConversations({ unassigned: true });
    const urls = fetchMock.mock.calls.map((c) => String((c as unknown[])[0]));
    expect(urls[0]).toMatch(/\/api\/v1\/conversations$/);
    expect(urls[1]).toMatch(/\/api\/v1\/conversations\?project_id=p\+1$/);
    expect(urls[2]).toMatch(/\/api\/v1\/conversations\?unassigned=true$/);
  });
});

describe("New project copy", () => {
  it("has Persian strings for the new project flow", () => {
    expect(UI_FA["New project"]).toBe("پروژه جدید");
    for (const key of ["Project name", "Cancel", "General (no project)", "Chat history of this project"]) {
      expect(UI_FA[key], key).toBeTruthy();
    }
  });

  it("no longer offers a global 'New Chat' / «گفتگوی جدید» button label in the chat UI", () => {
    const root = resolve(__dirname, "..");
    const files: string[] = [];
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        if (name === "node_modules" || name === ".next" || name === "tests") continue;
        const full = join(dir, name);
        if (statSync(full).isDirectory()) walk(full);
        else if (/\.(tsx?|css)$/.test(name)) files.push(full);
      }
    };
    for (const sub of ["components", "app", "hooks"]) walk(join(root, sub));
    const offenders = files.filter((f) => /\+ New Chat|گفتگوی جدید/.test(readFileSync(f, "utf8")));
    expect(offenders).toEqual([]);
    expect(readFileSync(join(root, "components/chat/ChatSidebar.tsx"), "utf8")).toContain("new-project-button");
  });
});
