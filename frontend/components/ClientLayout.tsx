"use client";

import { useState, useEffect, useCallback } from "react";
import { Navbar } from "@/components/Navbar";
import { AlertStack } from "@/components/AlertToast";
import { useAlerts, type ScannerAlert } from "@/lib/useAlerts";
import { useAuth } from "@/lib/useAuth";
import { supabase } from "@/lib/supabase";

export function ClientLayout({ children }: { children: React.ReactNode }) {
  const { tier, isLoggedIn } = useAuth();
  const [token, setToken] = useState<string | null>(null);
  const [toasts, setToasts] = useState<ScannerAlert[]>([]);

  // Get token once on mount
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setToken(session?.access_token ?? localStorage.getItem("token"));
    });
  }, [isLoggedIn]);

  const handleAlert = useCallback((alert: ScannerAlert) => {
    setToasts(prev => [alert, ...prev]);
  }, []);

  const { unreadCount } = useAlerts({ token, tier, onAlert: handleAlert });

  const dismissToast = useCallback((timestamp: string) => {
    setToasts(prev => prev.filter(a => a.timestamp !== timestamp));
  }, []);

  return (
    <>
      <Navbar unreadAlerts={unreadCount} />
      {children}
      <AlertStack alerts={toasts} onDismiss={dismissToast} />
    </>
  );
}
