"use client";
import { useState, useEffect } from "react";
import { supabase } from "./supabase";

export type UserTier = "visitor" | "free" | "retail" | "pro" | "enterprise";

export interface AuthUser {
  id: string;
  email: string;
  tier: UserTier;
}

function tierFromJwt(token: string): UserTier {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return (payload.tier as UserTier) || "free";
  } catch {
    return "free";
  }
}

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const resolve = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.user) {
        // Try to get tier from our backend /me endpoint
        try {
          const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
          const res = await fetch(`${API}/api/v1/auth/me`, {
            headers: { Authorization: `Bearer ${session.access_token}` },
          });
          if (res.ok) {
            const me = await res.json();
            setUser({ id: me.id, email: me.email, tier: me.tier || "free" });
            setLoading(false);
            return;
          }
        } catch {}
        setUser({ id: session.user.id, email: session.user.email || "", tier: "free" });
      } else {
        // Check localStorage demo token
        const token = localStorage.getItem("token");
        if (token) {
          const tier = tierFromJwt(token);
          setUser({ id: "demo", email: "demo@tradingcopilot.ai", tier });
        } else {
          setUser(null);
        }
      }
      setLoading(false);
    };

    resolve();

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session) {
        const token = localStorage.getItem("token");
        if (token) {
          setUser({ id: "demo", email: "demo@tradingcopilot.ai", tier: tierFromJwt(token) });
        } else {
          setUser(null);
        }
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  const isAtLeast = (required: UserTier): boolean => {
    const order: UserTier[] = ["visitor", "free", "retail", "pro", "enterprise"];
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
