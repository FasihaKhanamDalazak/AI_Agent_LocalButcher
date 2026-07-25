import { createContext, useContext } from "react";
import { useAuthState } from "../hooks/useAuthState.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const auth = useAuthState();
  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>;
}

/** @returns {{isAuthenticated: boolean, user: object|null, isLoadingUser: boolean, login: Function, register: Function, logout: Function}} */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
