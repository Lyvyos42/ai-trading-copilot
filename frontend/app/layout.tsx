import type { Metadata } from "next";
import "./globals.css";
import { ClientLayout } from "@/components/ClientLayout";
import { MarketBar } from "@/components/MarketBar";
import { KeepAlive } from "@/components/KeepAlive";

export const metadata: Metadata = {
  title: "AI Trading Copilot — Multi-Agent Trading Terminal",
  description:
    "80+ quantitative strategies powered by 6 specialized AI agents. Live market data, news intelligence, multi-agent debate — built for retail traders.",
  keywords: ["trading", "AI", "quantitative", "signals", "multi-agent", "LangGraph", "Claude"],
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
          <main className="pt-[72px]">{children}</main>
        </ClientLayout>
      </body>
    </html>
  );
}
