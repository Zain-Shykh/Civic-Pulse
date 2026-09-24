// The OQ5 hand-rolled data-fetching hook, shown once — docs/specs/
// phase-09-frontend-views.md's Plan. Reused unchanged by Submit, Stats, and
// Dashboard's list-fetch. Dashboard's per-row status action does NOT reuse
// this: this hook models exactly one in-flight call, and a row list can have
// several actions in flight simultaneously, each needing its own state keyed
// by complaint id — Dashboard keeps a small local record for that instead.

import { useCallback, useState } from "react";

import type { ApiError, ApiResult } from "../api/types";

export type CallState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; error: ApiError };

export function useApiCall<T, Args extends unknown[]>(
  fn: (...args: Args) => Promise<ApiResult<T>>,
): [CallState<T>, (...args: Args) => Promise<ApiResult<T>>] {
  const [state, setState] = useState<CallState<T>>({ status: "idle" });

  const run = useCallback(
    async (...args: Args) => {
      setState({ status: "loading" });
      const result = await fn(...args);
      setState(result.ok ? { status: "success", data: result.data } : { status: "error", error: result.error });
      return result;
    },
    [fn],
  );

  return [state, run];
}
