import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { RESEARCH_PUBLIC } from "@/lib/visibility";
import { MonolithShell, type RailSection } from "@/components/monolith/MonolithShell";
import { TruthLab } from "@/components/monolith/lab/TruthLab";
import { IconGrid, IconLock, IconShield, IconTarget } from "@/components/icons/GeoIcons";

export const metadata: Metadata = {
  title: "Strategy Truth Lab — Quant Neural Edge",
  description:
    "The anti-overfitting backtester. Describe a strategy in plain English, confirm the exact rules, and get a verdict measured on years the rules have never seen.",
};

const SECTIONS: RailSection[] = [
  { href: "#describe", label: "ASK", title: "Describe a strategy", Icon: IconTarget },
  { href: "#rules", label: "RULE", title: "Rules as understood", Icon: IconShield },
  { href: "#verdict", label: "VRDT", title: "Verdict", Icon: IconLock },
  { href: "#library", label: "LIB", title: "Tested strategies", Icon: IconGrid },
];

function first(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

export default function LabPage({ searchParams }: { searchParams: Record<string, string | string[] | undefined> }) {
  if (!RESEARCH_PUBLIC) notFound();                  // research stays private (owner 2026-11-14)
  return (
    <MonolithShell
      active="lab"
      sections={SECTIONS}
      status={["Sealed results: IEB research lab, 2026-11-14", "Test engine: not attached in this preview"]}
    >
      <TruthLab initialExample={first(searchParams.example)} initialStep={first(searchParams.step)} />
    </MonolithShell>
  );
}
