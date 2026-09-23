// docs/specs/phase-09-frontend-views.md, Deliverable (b). Never precomputes
// which status transitions are legal — every row always offers all four
// actions, always sends the PATCH, and renders whatever the backend actually
// says (200 updates the row, 409 renders its rejection inline). The backend's
// transition table (docs/CONTRACTS.md §2.2) is the only place that decision
// is made.
import { useEffect, useState } from "react";

import { describeApiError, listComplaints, updateStatus } from "../api/client";
import type { ApiError, Category, Priority, Status } from "../api/types";
import { useApiCall } from "../hooks/useApiCall";

const CATEGORIES: Category[] = ["water", "electricity", "sanitation", "roads", "streetlights", "other"];
const PRIORITIES: Priority[] = ["high", "normal", "low"];
const STATUSES: Status[] = ["open", "in_progress", "resolved", "rejected"];
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
    <div>
      <h2>Dashboard</h2>
      <div>
        <label>
          Category
          <select value={category} onChange={(e) => setCategory(e.target.value as Category | "")}>
            <option value="">All</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label>
          Priority
          <select value={priority} onChange={(e) => setPriority(e.target.value as Priority | "")}>
            <option value="">All</option>
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select value={status} onChange={(e) => setStatus(e.target.value as Status | "")}>
            <option value="">All</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
      </div>

      {listState.status === "loading" && <p>Loading…</p>}
      {listState.status === "error" && <p role="alert">{describeApiError(listState.error)}</p>}

      {listState.status === "success" && (
        <>
          <table>
            <tbody>
              {listState.data.items.map((complaint) => {
                const action = rowActions[complaint.id];
                return (
                  <tr key={complaint.id}>
                    <td>{complaint.location}</td>
                    <td>{complaint.category}</td>
                    <td>{complaint.priority}</td>
                    <td data-testid="status">{complaint.status}</td>
                    <td>
                      {STATUSES.map((s) => (
                        <button key={s} disabled={action?.loading} onClick={() => handleAction(complaint.id, s)}>
                          {s}
                        </button>
                      ))}
                      {action?.error && <span role="alert">{describeApiError(action.error)}</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div>
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Prev
            </button>
            <span>
              {" "}
              Page {listState.data.page}{" "}
            </span>
            <button
              disabled={listState.data.page * listState.data.page_size >= listState.data.total}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}
