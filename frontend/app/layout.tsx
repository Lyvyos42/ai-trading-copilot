import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/Navbar";
import { MarketBar } from "@/components/MarketBar";
import { KeepAlive } from "@/components/KeepAlive";

export const metadata: Metadata = {
  title: "AI Trading Copilot — Bloomberg-Style Multi-Agent Terminal",
  description:
    "80+ quantitative strategies powered by 6 specialized AI agents. Live market data, news intelligence, multi-agent debate — built for retail traders.",
  keywords: ["trading", "AI", "quantitative", "signals", "Bloomberg", "LangGraph", "Claude"],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background antialiased">
        {/* Top nav bar */}
        <Navbar />
        {/* Scrolling market ticker — sits below navbar */}
        <div className="fixed top-10 left-0 right-0 z-40">
          <MarketBar />
        </div>
        <KeepAlive />
        {/* Page content — offset for both bars (navbar=40px, marketbar=32px) */}
        <main className="pt-[72px]">{children}</main>
      </body>
    </html>
  );
}
