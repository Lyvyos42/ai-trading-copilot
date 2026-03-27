"use client";
import { useState } from "react";
import { sendSignalFeedback } from "@/lib/api";

interface Props {
  signalId: string;
  ticker?: string;
}

export default function SignalFeedback({ signalId, ticker }: Props) {
  const [feedback, setFeedback] = useState<"THUMBS_UP" | "THUMBS_DOWN" | null>(null);
  const [sending, setSending] = useState(false);

  async function handleFeedback(type: "THUMBS_UP" | "THUMBS_DOWN") {
    if (sending || feedback) return;
    setSending(true);
    try {
      await sendSignalFeedback(signalId, type, ticker);
      setFeedback(type);
    } catch {
      // silent
    } finally {
      setSending(false);
    }
  }

  return (
    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
      <button
        onClick={() => handleFeedback("THUMBS_UP")}
        disabled={!!feedback || sending}
        style={{
          background: feedback === "THUMBS_UP" ? "hsl(var(--primary) / 0.15)" : "hsl(var(--surface-2))",
          border: feedback === "THUMBS_UP" ? "1px solid hsl(var(--primary) / 0.3)" : "1px solid hsl(var(--border))",
          borderRadius: 4,
          padding: "4px 8px",
          cursor: feedback ? "default" : "pointer",
          color: feedback === "THUMBS_UP" ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))",
          fontSize: 13,
          transition: "all 0.15s",
          opacity: feedback && feedback !== "THUMBS_UP" ? 0.3 : 1,
        }}
        title="Good signal"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
        </svg>
      </button>
      <button
        onClick={() => handleFeedback("THUMBS_DOWN")}
        disabled={!!feedback || sending}
        style={{
          background: feedback === "THUMBS_DOWN" ? "hsl(0 70% 50% / 0.15)" : "hsl(var(--surface-2))",
          border: feedback === "THUMBS_DOWN" ? "1px solid hsl(0 70% 50% / 0.3)" : "1px solid hsl(var(--border))",
          borderRadius: 4,
          padding: "4px 8px",
          cursor: feedback ? "default" : "pointer",
          color: feedback === "THUMBS_DOWN" ? "hsl(0 70% 50%)" : "hsl(var(--muted-foreground))",
          fontSize: 13,
          transition: "all 0.15s",
          opacity: feedback && feedback !== "THUMBS_DOWN" ? 0.3 : 1,
        }}
        title="Bad signal"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17" />
        </svg>
      </button>
    </div>
  );
}
