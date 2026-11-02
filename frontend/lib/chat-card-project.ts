import { createContext, useContext } from "react";

import { getCurrentProjectId } from "@/lib/current-project";

/**
 * Project a rendered chat card belongs to. `undefined` = follow the active project (default);
 * `null` = the open conversation is a legacy chat with no project, so its cards must not write into
 * (or download for) whichever project happens to be active.
 */
export const ChatCardProjectContext = createContext<string | null | undefined>(undefined);

export function useChatCardProjectId(): string | null {
  const ctx = useContext(ChatCardProjectContext);
  return ctx === undefined ? getCurrentProjectId() : ctx;
}
