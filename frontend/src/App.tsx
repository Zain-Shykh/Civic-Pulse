import { useState } from "react";

import Dashboard from "./pages/Dashboard";
import Stats from "./pages/Stats";
import Submit from "./pages/Submit";

type View = "submit" | "dashboard" | "stats";

export default function App() {
  const [view, setView] = useState<View>("submit");

  return (
    <div>
      <nav>
        {/* "New complaint", not "Submit" — the Submit view's own form button
            is also named "Submit"; two buttons with the same accessible
            name on screen at once is a real ambiguity, not just a test
            artifact (found via the manual browser walkthrough). */}
        <button onClick={() => setView("submit")}>New complaint</button>
        <button onClick={() => setView("dashboard")}>Dashboard</button>
        <button onClick={() => setView("stats")}>Stats</button>
      </nav>
      {view === "submit" && <Submit />}
      {view === "dashboard" && <Dashboard />}
      {view === "stats" && <Stats />}
    </div>
  );
}
