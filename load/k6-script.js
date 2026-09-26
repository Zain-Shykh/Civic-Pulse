// Load test for Phase 11b's HPA/VPA loop (docs/specs/phase-11b-failfast-and-vpa-verification.md).
//
// Targets POST /api/complaints (real validation + triage + DB write per
// request). That endpoint is rate-limited to 10 req/60s per source IP
// (docs/CONTRACTS.md, Phase 8), keyed on the X-Real-IP header falling back
// to the raw connecting socket IP. A single external k6 process cannot
// simulate many distinct clients here: Traefik overwrites/ignores any
// client-supplied X-Real-IP with its own view of the real connecting
// address, so every request from outside the cluster shares one rate-limit
// bucket regardless of VU count (confirmed directly against the live
// cluster — see As-Built).
//
// Real IP diversity therefore comes from running this script as many
// separate Kubernetes Job pods (load/k6-job.yaml), each with its own real,
// distinct pod IP from the cluster network — no header spoofing. Each pod
// runs exactly one VU here, sleeping ~6.5s between requests (under 10/60s
// for its own IP); aggregate throughput scales with the Job's
// `parallelism`, calibrated live during Verification.
//
// BASE_URL/HOST_HEADER let the same script also be smoke-tested directly
// from the host against the published Ingress port (HOST_HEADER set,
// several VUs — fine for a quick sanity check, not for the real load run).

import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://backend:8000";
const HOST_HEADER = __ENV.HOST_HEADER || "";

const COMPLAINTS = [
  { text: "Water supply has been stopped in our street for three days now, please resolve urgently.", location: "Sector G-9, Islamabad" },
  { text: "Streetlight outside our house has not worked in two weeks, it is very dark and unsafe at night.", location: "Model Town, Lahore" },
  { text: "Garbage has not been collected from our lane in over a week and is starting to smell badly.", location: "Gulshan-e-Iqbal, Karachi" },
  { text: "There is a large pothole on the main road that has already caused one bike accident.", location: "F-10 Markaz, Islamabad" },
  { text: "Sewerage line is overflowing near the local mosque, creating a health hazard for the area.", location: "Satellite Town, Rawalpindi" },
];

export const options = {
  vus: Number(__ENV.VUS) || 1,
  duration: __ENV.DURATION || "4m",
};

export default function () {
  const complaint = COMPLAINTS[Math.floor(Math.random() * COMPLAINTS.length)];
  const headers = { "Content-Type": "application/json" };
  if (HOST_HEADER) headers.Host = HOST_HEADER;
  const res = http.post(`${BASE_URL}/api/complaints`, JSON.stringify(complaint), { headers });
  check(res, { "status is 201": (r) => r.status === 201 });
  sleep(6.5);
}
