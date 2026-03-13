import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/Navbar";

export const metadata: Metadata = {
  title: "AI Trading Copilot — Multi-Agent Signal Platform",
  description:
    "80+ quantitative strategies from '151 Trading Strategies' powered by 6 specialized AI agents. Multi-agent debate, explainable signals, portfolio risk management.",
  keywords: ["trading", "AI", "quantitative", "signals", "LangGraph", "Claude"],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background font-sans antialiased">
        <Navbar />
        <main className="pt-14">{children}</main>
      </body>
    </html>
  );
}
