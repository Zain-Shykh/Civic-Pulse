// docs/specs/phase-09c-visual-redesign.md's Plan §12. Accessibility/Privacy/
// Contact are plain inert labels, not <a>s — no destination pages approved
// yet (see the spec's Non-goals).
export default function Footer() {
  return (
    <footer className="border-t border-border bg-muted">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2 px-4 py-4 text-sm text-ink-muted">
        <p>© {new Date().getFullYear()} CivicPulse. Not affiliated with emergency services.</p>
        <div className="flex gap-4">
          <span>Accessibility</span>
          <span>Privacy</span>
          <span>Contact</span>
        </div>
      </div>
    </footer>
  );
}
