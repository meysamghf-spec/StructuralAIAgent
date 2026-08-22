"use client";

import { AuthGate } from "@/components/AuthGate";
import { AppShell } from "@/components/AppShell";
import { AuthProvider } from "@/hooks/useAuth";
import type { ReactNode } from "react";

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <AuthGate>
        <AppShell>{children}</AppShell>
      </AuthGate>
    </AuthProvider>
  );
}
