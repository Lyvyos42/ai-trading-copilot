import type { Metadata } from "next";
import "./globals.css";
import { ClientLayout } from "@/components/ClientLayout";
import { MarketBar } from "@/components/MarketBar";
import { KeepAlive } from "@/components/KeepAlive";

export const metadata: Metadata = {
  title: "Trading Copilot — Quant Neural Edge",
  description:
    "Rule-based trading signals: nine checks vote on every signal. Consensus Score, the reasons behind it, and the historical outcome rate of its score band.",
  keywords: ["trading", "quantitative", "signals", "consensus score", "rule-based"],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background antialiased">
        {/* Scrolling market ticker — sits below navbar */}
        <div className="fixed top-10 left-0 right-0 z-40">
          <MarketBar />
        </div>
        <KeepAlive />
        {/* ClientLayout renders Navbar + page content + alert toasts */}
        <ClientLayout>
          <main className="pt-[var(--chrome-h)]">{children}</main>
        </ClientLayout>
      </body>
    </html>
  );
}
