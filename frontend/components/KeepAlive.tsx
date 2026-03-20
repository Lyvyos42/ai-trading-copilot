"use client";

import { useEffect } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const INTERVAL_MS = 14 * 60 * 1000; // 14 minutes

/** Pings the backend every 14 min to prevent Render free tier from sleeping. */
export function KeepAlive() {
  useEffect(() => {
    const ping = () => fetch(`${API}/health`).catch(() => {});
    const id = setInterval(ping, INTERVAL_MS);
    return () => clearInterval(id);
  }, []);
  return null;
}
