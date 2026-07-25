import { useCallback, useEffect, useState } from "react";
import * as api from "../services/api.js";
import { setUnauthorizedHandler } from "../services/httpClient.js";
import { getToken, setToken, clearToken } from "../utils/authStorage.js";

/**
 * The actual auth state machine — token + current user + login/register/
 * logout. Not imported directly outside AuthContext; everything else goes
 * through useAuth() (context/AuthContext.jsx) so there's exactly one
 * instance shared across the app, not a fresh one per component.
 */
export function useAuthState() {
  const [token, setTokenState] = useState(() => getToken());
  const [user, setUser] = useState(null);
  const [isLoadingUser, setIsLoadingUser] = useState(false);

  const isAuthenticated = Boolean(token);

  const logout = useCallback(() => {
    clearToken();
    setTokenState(null);
    setUser(null);
  }, []);

  // Global 401 handling: any request anywhere in the app that comes back
  // unauthorized ends the session the same way an explicit logout does.
  useEffect(() => {
    setUnauthorizedHandler(logout);
  }, [logout]);

  // A token surviving from localStorage (page refresh) hasn't been
  // confirmed valid yet — fetch the profile once to both validate it and
  // populate `user`. If it's stale/expired, the 401 handler above logs
  // out automatically.
  useEffect(() => {
    if (!token || user) return;
    let cancelled = false;
    setIsLoadingUser(true);
    api
      .getCurrentUser()
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch(() => {
        if (!cancelled) logout();
      })
      .finally(() => {
        if (!cancelled) setIsLoadingUser(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, user, logout]);

  const login = useCallback(async (email, password) => {
    const accessToken = await api.login(email, password);
    setToken(accessToken);
    setTokenState(accessToken);
  }, []);

  const register = useCallback(async (data) => {
    const accessToken = await api.register(data);
    setToken(accessToken);
    setTokenState(accessToken);
  }, []);

  return { isAuthenticated, user, isLoadingUser, login, register, logout };
}
