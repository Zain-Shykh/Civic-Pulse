// Shows the full record for one complaint. Renders whatever it's given —
// no fetching of its own; the caller (Dashboard) already has the full
// Complaint object from listComplaints, so this stays purely presentational.
import type { Complaint } from "../api/types";
import { Badge } from "./ui/badge";

interface ComplaintDetailModalProps {
  complaint: Complaint;
  onClose: () => void;
}

export default function ComplaintDetailModal({ complaint, onClose }: ComplaintDetailModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="complaint-detail-heading"
        className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-lg border border-border bg-background p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <h3 id="complaint-detail-heading" className="text-lg font-semibold text-ink">
            Complaint detail
          </h3>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-ink-secondary hover:bg-muted"
          >
            ✕
          </button>
        </div>

        <div className="mt-4 flex flex-wrap gap-1">
          <Badge variant={complaint.priority}>{complaint.priority}</Badge>
          <Badge variant={complaint.status}>{complaint.status}</Badge>
        </div>

        <dl className="mt-4 space-y-3 text-sm">
          <div>
            <dt className="font-medium text-ink-secondary">Text</dt>
            <dd className="mt-1 whitespace-pre-wrap text-ink">{complaint.text}</dd>
          </div>
          <div>
            <dt className="font-medium text-ink-secondary">Location</dt>
            <dd className="mt-1 text-ink">{complaint.location}</dd>
          </div>
          <div>
            <dt className="font-medium text-ink-secondary">Category</dt>
            <dd className="mt-1 text-ink">{complaint.category}</dd>
          </div>
          <div>
            <dt className="font-medium text-ink-secondary">Reporter contact</dt>
            <dd className="mt-1 text-ink">{complaint.reporter_contact ?? "—"}</dd>
          </div>
          <div>
            <dt className="font-medium text-ink-secondary">AI summary</dt>
            <dd className="mt-1 text-ink">{complaint.ai_summary ?? "—"}</dd>
          </div>
          <div>
            <dt className="font-medium text-ink-secondary">Triaged by</dt>
            <dd className="mt-1 text-ink">
              {complaint.triaged_by} ({complaint.triage_latency_ms}ms)
            </dd>
          </div>
          <div>
            <dt className="font-medium text-ink-secondary">Created</dt>
            <dd className="mt-1 text-ink">{new Date(complaint.created_at).toLocaleString()}</dd>
          </div>
          <div>
            <dt className="font-medium text-ink-secondary">Last updated</dt>
            <dd className="mt-1 text-ink">{new Date(complaint.updated_at).toLocaleString()}</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}