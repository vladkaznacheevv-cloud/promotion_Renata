/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { DEV_MOCKS } from "../api/http";
import { login as loginRequest, getMe, logout as logoutRequest } from "../api/auth";

const AUTH_TOKEN_KEY = "crm_auth_token";
const AUTH_USER_KEY = "crm_auth_user";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(() => {
    const raw = localStorage.getItem(AUTH_USER_KEY);
    return raw ? JSON.parse(raw) : null;
  });
  const [token, setToken] = useState(() => localStorage.getItem(AUTH_TOKEN_KEY));
  const [loading, setLoading] = useState(true);

  const saveAuth = useCallback((nextToken, user) => {
    localStorage.setItem(AUTH_TOKEN_KEY, nextToken);
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
    setToken(nextToken);
    setCurrentUser(user);
  }, []);

  const clearAuth = useCallback(() => {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
    setToken(null);
    setCurrentUser(null);
  }, []);

  const login = useCallback(async (email, password) => {
    const result = await loginRequest({ email, password });
    saveAuth(result.access_token, result.user);
    return result.user;
  }, [saveAuth]);

  const logout = useCallback(async () => {
    try {
      await logoutRequest();
    } catch {
      // ignore network errors on logout
    }
    clearAuth();
  }, [clearAuth]);

  useEffect(() => {
    let active = true;

    (async () => {
      if (DEV_MOCKS) {
        if (!token || !currentUser) {
          saveAuth("dev", { id: 0, email: "dev@local", role: "admin" });
        }
        setLoading(false);
        return;
      }

      if (!token) {
        setLoading(false);
        return;
      }

      try {
        const me = await getMe();
        if (!active) return;
        saveAuth(token, me.user);
      } catch {
        clearAuth();
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
    };
  }, [token, currentUser, saveAuth, clearAuth]);

  const value = useMemo(
    () => ({
      currentUser,
      token,
      loading,
      isAuthenticated: Boolean(currentUser && token),
      login,
      logout,
    }),
    [currentUser, token, loading, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
