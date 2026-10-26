"use client";

import { useAuth } from "@/hooks/useAuth";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { PUBLIC_PATHS as LEGAL_PATHS } from "@/lib/legal-content";

const PUBLIC_PATHS = new Set<string>(["/", "/login", "/register", ...LEGAL_PATHS]);

export function AuthGate({ children }: { children: ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const isPublic = PUBLIC_PATHS.has(pathname.length > 1 ? pathname.replace(/\/$/, "") : pathname);

  useEffect(() => {
    if (loading || isPublic || isAuthenticated) {
      return;
    }
    const next = pathname === "/" ? "" : `?next=${encodeURIComponent(pathname)}`;
    router.replace(`/login${next}`);
  }, [isAuthenticated, isPublic, loading, pathname, router]);

  if (loading && !isPublic) {
    return (
      <div className="auth-loading">
        <p className="muted">Checking authentication…</p>
      </div>
    );
  }

  if (!isPublic && !isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}
