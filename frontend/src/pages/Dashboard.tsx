// docs/specs/phase-09-frontend-views.md, Deliverable (b). Never precomputes
// which status transitions are legal — every row always offers all four
// actions, always sends the PATCH, and renders whatever the backend actually
// says (200 updates the row, 409 renders its rejection inline). The backend's
// transition table (docs/CONTRACTS.md §2.2) is the only place that decision
// is made. Restyled in docs/specs/phase-09c-visual-redesign.md — same logic,
// new markup only; filter <select>s stay native per that spec's OQ2.
import { useEffect, useState } from "react";

import { describeApiError, listComplaints, updateStatus } from "../api/client";
import { CATEGORIES, PRIORITIES, STATUSES, type ApiError, type Category, type Priority, type Status } from "../api/types";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { useApiCall } from "../hooks/useApiCall";

const PAGE_SIZE = 20;

export default function Dashboard() {
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState<Category | "">("");
  const [priority, setPriority] = useState<Priority | "">("");
  const [status, setStatus] = useState<Status | "">("");
  const [listState, runList] = useApiCall(listComplaints);
  const [rowActions, setRowActions] = useState<Record<string, { loading: boolean; error?: ApiError }>>({});

  useEffect(() => {
    runList({
      page,
      page_size: PAGE_SIZE,
      category: category || undefined,
      priority: priority || undefined,
      status: status || undefined,
    });
  }, [page, category, priority, status, runList]);

  async function handleAction(id: string, next: Status) {
    setRowActions((prev) => ({ ...prev, [id]: { loading: true } }));
    const result = await updateStatus(id, next);
    if (result.ok) {
      setRowActions((prev) => ({ ...prev, [id]: { loading: false } }));
      await runList({
        page,
        page_size: PAGE_SIZE,
        category: category || undefined,
        priority: priority || undefined,
        status: status || undefined,
      });
    } else {
      setRowActions((prev) => ({ ...prev, [id]: { loading: false, error: result.error } }));
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <h2 className="text-2xl font-semibold text-ink">Dashboard</h2>
      <div className="mt-4 flex flex-wrap gap-4">
        <label className="flex items-center gap-2 text-sm text-ink">
          Category
          <select
            className="rounded-md border border-border bg-background px-2 py-1"
            value={category}
            onChange={(e) => setCategory(e.target.value as Category | "")}
          >
            <option value="">All</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm text-ink">
          Priority
          <select
            className="rounded-md border border-border bg-background px-2 py-1"
            value={priority}
            onChange={(e) => setPriority(e.target.value as Priority | "")}
          >
            <option value="">All</option>
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm text-ink">
          Status
          <select
            className="rounded-md border border-border bg-background px-2 py-1"
            value={status}
            onChange={(e) => setStatus(e.target.value as Status | "")}
          >
            <option value="">All</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
      </div>

      {listState.status === "loading" && <p className="mt-4">Loading…</p>}
      {listState.status === "error" && (
        <p role="alert" className="mt-4 text-priority-high">
          {describeApiError(listState.error)}
        </p>
      )}

      {listState.status === "success" && listState.data.items.length === 0 && (
        <p className="mt-4 text-ink-secondary">
          No complaints match the current filters.
        </p>
      )}

      {listState.status === "success" && listState.data.items.length > 0 && (
        <>
          <table className="mt-4 w-full border-collapse text-left text-sm">
            <tbody>
              {listState.data.items.map((complaint) => {
                const action = rowActions[complaint.id];
                return (
                  <tr key={complaint.id} className="border-b border-border">
                    <td className="py-2 pr-4">{complaint.location}</td>
                    <td className="py-2 pr-4">{complaint.category}</td>
                    <td className="py-2 pr-4">
                      <Badge variant={complaint.priority}>{complaint.priority}</Badge>
                    </td>
                    <td className="py-2 pr-4" data-testid="status">
                      <Badge variant={complaint.status}>{complaint.status}</Badge>
                    </td>
                    <td className="py-2">
                      <div className="flex flex-wrap gap-1">
                        {STATUSES.map((s) => (
                          <Button
                            key={s}
                            size="sm"
                            variant="outline"
                            disabled={action?.loading}
                            onClick={() => handleAction(complaint.id, s)}
                          >
                            {s}
                          </Button>
                        ))}
                      </div>
                      {action?.error && (
                        <span role="alert" className="mt-1 block text-priority-high">
                          {describeApiError(action.error)}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="mt-4 flex items-center gap-3">
            <Button variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Prev
            </Button>
            <span className="text-sm text-ink-secondary">Page {listState.data.page}</span>
            <Button
              variant="outline"
              disabled={listState.data.page * listState.data.page_size >= listState.data.total}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
