"use client";
import { createContext, useContext } from "react";

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  tenant_id: string;
}

export interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  login: (token: string, user: AuthUser) => void;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  login: () => {},
  logout: () => {},
});

export const useAuth = () => useContext(AuthContext);

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("naqla_token");
}

export function setStoredToken(token: string) {
  localStorage.setItem("naqla_token", token);
}

export function clearStoredToken() {
  localStorage.removeItem("naqla_token");
  localStorage.removeItem("naqla_user");
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const u = localStorage.getItem("naqla_user");
  return u ? JSON.parse(u) : null;
}

export function setStoredUser(user: AuthUser) {
  localStorage.setItem("naqla_user", JSON.stringify(user));
}
