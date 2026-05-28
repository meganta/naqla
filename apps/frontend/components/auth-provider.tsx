"use client";
import { useState, useEffect, ReactNode } from "react";
import { AuthContext, AuthUser, getStoredToken, getStoredUser, setStoredToken, setStoredUser, clearStoredToken } from "@/lib/auth";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    const t = getStoredToken();
    const u = getStoredUser();
    if (t && u) { setToken(t); setUser(u); }
  }, []);

  function login(t: string, u: AuthUser) {
    setToken(t); setUser(u);
    setStoredToken(t); setStoredUser(u);
  }

  function logout() {
    setToken(null); setUser(null);
    clearStoredToken();
  }

  return (
    <AuthContext.Provider value={{ token, user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
