"use client";

import {
  fetchCurrentUser,
  fetchFeatureAccess,
  loginUser,
  logoutRemote,
  registerUser,
  restoreSession,
  type FeatureAccessSummary,
  type UserResponse,
} from "@/lib/auth-api";
import { clearAuthSession, getStoredAuthToken, hasRememberHint } from "@/lib/auth-session";
import { bootstrapAuth, isSessionRejected } from "@/lib/auth-bootstrap";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

type AuthContextValue = {
  user: UserResponse | null;
  features: FeatureAccessSummary | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string, remember?: boolean) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [features, setFeatures] = useState<FeatureAccessSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const token = getStoredAuthToken();
    if (!token) {
      setUser(null);
      setFeatures(null);
      return;
    }
    const me = await fetchCurrentUser();
    setUser(me);
    try {
      setFeatures(await fetchFeatureAccess());
    } catch (error) {
      if (isSessionRejected(error)) throw error;
      /* feature access is advisory; a slow/failed call must not sign the user out */
    }
  }, []);

  useEffect(() => {
    let active = true;
    let unloading = false;
    const onPageHide = () => {
      unloading = true;
    };
    window.addEventListener("pagehide", onPageHide);
    window.addEventListener("beforeunload", onPageHide);
    async function bootstrap() {
      const result = await bootstrapAuth({
        getToken: getStoredAuthToken,
        hasRememberHint,
        restoreSession,
        fetchCurrentUser,
        clearSession: clearAuthSession,
        isUnloading: () => unloading || !active,
      });
      if (!active) return;
      if (result.status === "authenticated") {
        setUser(result.user);
      } else {
        setUser(null);
        setFeatures(null);
      }
      setLoading(false);
      if (result.status === "authenticated") {
        fetchFeatureAccess()
          .then((summary) => {
            if (active) setFeatures(summary);
          })
          .catch(() => {
            /* advisory only */
          });
      }
    }
    void bootstrap();
    return () => {
      active = false;
      window.removeEventListener("pagehide", onPageHide);
      window.removeEventListener("beforeunload", onPageHide);
    };
  }, []);

  const login = useCallback(
    async (email: string, password: string, remember = false) => {
      const response = await loginUser({ email, password, remember_me: remember });
      setUser(response.user);
      const featureSummary = await fetchFeatureAccess();
      setFeatures(featureSummary);
    },
    [],
  );

  const register = useCallback(
    async (email: string, password: string, displayName?: string) => {
      const response = await registerUser({
        email,
        password,
        display_name: displayName,
      });
      setUser(response.user);
      const featureSummary = await fetchFeatureAccess();
      setFeatures(featureSummary);
    },
    [],
  );

  const logout = useCallback(() => {
    void logoutRemote();
    clearAuthSession();
    setUser(null);
    setFeatures(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      features,
      loading,
      isAuthenticated: user !== null,
      login,
      register,
      logout,
      refresh,
    }),
    [user, features, loading, login, register, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
