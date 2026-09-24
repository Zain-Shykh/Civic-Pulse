import { useState } from "react";

import Footer from "./components/Footer";
import Header from "./components/Header";
import Dashboard from "./pages/Dashboard";
import Home from "./pages/Home";
import Stats from "./pages/Stats";
import Submit from "./pages/Submit";

export type View = "home" | "submit" | "dashboard" | "stats";

export default function App() {
  // docs/specs/phase-09c-visual-redesign.md's Plan §16 — defaults to "home"
  // now that a landing view exists, not "submit" as Phase 9 had it.
  const [view, setView] = useState<View>("home");

  return (
    <div className="flex min-h-screen flex-col">
      <Header view={view} onNavigate={setView} />
      <main className="flex-1">
        {view === "home" && <Home onNavigate={setView} />}
        {view === "submit" && <Submit />}
        {view === "dashboard" && <Dashboard />}
        {view === "stats" && <Stats />}
      </main>
      <Footer />
    </div>
  );
}
