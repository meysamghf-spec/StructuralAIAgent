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
    const [me, featureSummary] = await Promise.all([
      fetchCurrentUser(),
      fetchFeatureAccess(),
    ]);
    setUser(me);
    setFeatures(featureSummary);
  }, []);

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      try {
        if (!getStoredAuthToken() && hasRememberHint()) {
          await restoreSession(); // "remember me": the httpOnly cookie brings the session back
        }
        if (getStoredAuthToken()) {
          await refresh();
        }
      } catch {
        clearAuthSession();
        if (active) {
          setUser(null);
          setFeatures(null);
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }
    void bootstrap();
    return () => {
      active = false;
    };
  }, [refresh]);

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
