"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { WS_URL } from "./api";

export interface ScannerAlert {
  id?:        string;
  ticker:     string;
  direction:  "LONG" | "SHORT";
  confidence: number;
  summary:    string;
  entry_hint: number;
  timestamp:  string;
  read?:      boolean;
}

interface UseAlertsOptions {
  token:     string | null;
  tier:      string | null;
  onAlert?:  (alert: ScannerAlert) => void;
}

const PREMIUM_TIERS = new Set(["pro", "enterprise", "admin"]);

export function useAlerts({ token, tier, onAlert }: UseAlertsOptions) {
  const [alerts,      setAlerts]      = useState<ScannerAlert[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [connected,   setConnected]   = useState(false);
  const wsRef   = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isPremium = tier ? PREMIUM_TIERS.has(tier) : false;

  const markRead = useCallback((timestamp: string) => {
    setAlerts(prev => prev.map(a => a.timestamp === timestamp ? { ...a, read: true } : a));
    setUnreadCount(prev => Math.max(0, prev - 1));
  }, []);

  const markAllRead = useCallback(() => {
    setAlerts(prev => prev.map(a => ({ ...a, read: true })));
    setUnreadCount(0);
  }, []);

  useEffect(() => {
    if (!isPremium) return;  // Only connect for premium users

    function connect() {
      const url = token ? `${WS_URL}/ws/v1/signals/stream?token=${token}` : `${WS_URL}/ws/v1/signals/stream`;
      const ws  = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "alert") {
            const alert: ScannerAlert = {
              ticker:     msg.ticker,
              direction:  msg.direction,
              confidence: msg.confidence,
              summary:    msg.summary,
              entry_hint: msg.entry_hint,
              timestamp:  msg.timestamp,
              read:       false,
            };
            setAlerts(prev => [alert, ...prev.slice(0, 49)]);  // keep last 50
            setUnreadCount(prev => prev + 1);
            onAlert?.(alert);
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        setConnected(false);
        // Reconnect after 10s
        reconnectTimer.current = setTimeout(connect, 10_000);
      };

      ws.onerror = () => ws.close();
    }

    connect();

    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [isPremium, token]);  // eslint-disable-line react-hooks/exhaustive-deps

  return { alerts, unreadCount, connected, markRead, markAllRead };
}
