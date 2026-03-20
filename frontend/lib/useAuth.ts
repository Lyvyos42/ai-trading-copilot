"use client";
import { useState, useEffect } from "react";
import { supabase } from "./supabase";

export type UserTier = "visitor" | "free" | "retail" | "pro" | "enterprise" | "admin";

export interface AuthUser {
  id: string;
  email: string;
  tier: UserTier;
}

function parseLocalToken(token: string): { id: string; email: string; tier: UserTier } | null {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    // Reject expired tokens
    if (payload.exp && payload.exp * 1000 < Date.now()) return null;
    const email = payload.email || payload.sub || "demo@tradingcopilot.ai";
    const tier   = (payload.tier as UserTier) || "free";
    const id     = payload.sub || "demo";
    return { id, email, tier };
  } catch {
    return null;
  }
}

async function resolveSession(): Promise<AuthUser | null> {
  const { data: { session } } = await supabase.auth.getSession();

  if (session?.user) {
    try {
      const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${API}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (res.ok) {
        const me = await res.json();
        return { id: me.id, email: me.email, tier: me.tier || "free" };
      }
    } catch {}
    // Fallback: use Supabase session data directly
    return { id: session.user.id, email: session.user.email || "", tier: "free" };
  }

  // No Supabase session — check localStorage (demo or legacy token)
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  if (token) {
    const parsed = parseLocalToken(token);
    if (parsed) return parsed;
    // Token is expired — clean it up
    localStorage.removeItem("token");
  }

  return null;
}

export function useAuth() {
  const [user, setUser]       = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    resolveSession().then((u) => {
      if (!cancelled) { setUser(u); setLoading(false); }
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (cancelled) return;

      if (session?.user) {
        // Auth state changed to signed-in — re-resolve to get tier from /me
        resolveSession().then((u) => { if (!cancelled) setUser(u); });
      } else {
        // Signed out — check localStorage fallback
        const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
        if (token) {
          const parsed = parseLocalToken(token);
          setUser(parsed);
        } else {
          setUser(null);
        }
      }
    });

    return () => {
      cancelled = true;
      subscription.unsubscribe();
    };
  }, []);

  const isAtLeast = (required: UserTier): boolean => {
    const order: UserTier[] = ["visitor", "free", "retail", "pro", "enterprise", "admin"];
    const userIdx = order.indexOf(user?.tier ?? "visitor");
    const reqIdx  = order.indexOf(required);
    return userIdx >= reqIdx;
  };

  return {
    user,
    loading,
    tier: user?.tier ?? "visitor",
    isLoggedIn: !!user,
    isAtLeast,
  };
}
