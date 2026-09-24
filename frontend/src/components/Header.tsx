// docs/specs/phase-09c-visual-redesign.md's Plan §11. View-switching stays
// lifted in App.tsx (Phase 9's OQ1, unchanged) — Header only renders the
// active view and calls back up, it never owns navigation state itself.
import type { View } from "../App";
import { Button } from "./ui/button";

const NAV_ITEMS: { view: View; label: string }[] = [
  { view: "home", label: "Home" },
  { view: "submit", label: "Report an issue" },
  { view: "dashboard", label: "Dashboard" },
  { view: "stats", label: "Stats" },
];

export default function Header({ view, onNavigate }: { view: View; onNavigate: (view: View) => void }) {
  return (
    <header className="bg-primary text-white">
      <div className="mx-auto flex max-w-5xl items-center gap-4 px-4 py-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white">
          <svg viewBox="0 0 24 24" className="h-5 w-5 text-primary" fill="none" aria-hidden="true">
            <path
              d="M2 12h4l1.5-4 3 8 2-10 2.5 6H22"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <span className="text-lg font-semibold">CivicPulse</span>
        <nav className="ml-auto flex gap-1">
          {NAV_ITEMS.map((item) => (
            <Button
              key={item.view}
              variant="ghost"
              className={`rounded-none border-b-2 text-white hover:text-white ${
                view === item.view ? "border-emblem" : "border-transparent"
              }`}
              onClick={() => onNavigate(item.view)}
            >
              {item.label}
            </Button>
          ))}
        </nav>
      </div>
    </header>
  );
}
