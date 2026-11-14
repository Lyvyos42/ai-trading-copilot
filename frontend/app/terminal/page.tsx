import type { Metadata } from "next";
import { MonolithShell, type RailSection } from "@/components/monolith/MonolithShell";
import { LiveTerminal } from "@/components/monolith/terminal/LiveTerminal";
import {
  IconBands,
  IconCalendar,
  IconCrowd,
  IconOdds,
  IconSignal,
  IconWindows,
} from "@/components/icons/GeoIcons";

export const metadata: Metadata = {
  title: "Live Terminal — Quant Neural Edge",
  description:
    "Validated, rule-based signals shown live with their record: noise-area bands on USTEC and US500, big-move windows, the calendar, crowd positioning and prediction-market odds.",
};

const SECTIONS: RailSection[] = [
  { href: "#chart", label: "BAND", title: "Noise-area chart", Icon: IconBands },
  { href: "#signals", label: "SIGS", title: "Validated signals", Icon: IconSignal },
  { href: "#windows", label: "WNDW", title: "Big-move windows", Icon: IconWindows },
  { href: "#calendar", label: "CAL", title: "Calendar", Icon: IconCalendar },
  { href: "#positioning", label: "CRWD", title: "Crowd positioning", Icon: IconCrowd },
  { href: "#odds", label: "ODDS", title: "Market odds", Icon: IconOdds },
];

export default function TerminalPage() {
  return (
    <MonolithShell
      active="terminal"
      sections={SECTIONS}
      status={["Mock session 13:40 New York", "Feed: frontend mock, no live prices"]}
    >
      <LiveTerminal />
    </MonolithShell>
  );
}
