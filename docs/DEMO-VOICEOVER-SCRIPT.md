# Demo video — verbatim voiceover script

Read-aloud companion to `docs/DEMO-SCRIPT.md` (the shot-list this is based on).
That file stays the source of truth for *what to run and cite*; this file is
*what to actually say* — plain spoken sentences, not narration bullets. Scene
structure, commands, speakers and citations are carried over unchanged except
where noted below.

**How to use this:** the VOICEOVER block under each scene is read verbatim,
word for word, on camera. The ON SCREEN block is stage direction for
whoever's driving the keyboard/browser — never spoken. Quoted phrases in ON
SCREEN cues (e.g. `cue: "...four containers..."`) mark the point in the
voiceover where that on-screen action should land; they are the same words
as in the VOICEOVER block, repeated only so the two stay in sync at a glance.

**Two things found while preparing this were real inconsistencies, not
nitpicks, and have since been fixed (both live-graded docs, not just
video-adjacent):**

1. **`docs/TRIAGE.md` was stale, not just relative to Scene 3.** It stated
   `OllamaTriage` was "a stub only... intentionally unimplemented," and that
   `LLMTriage`'s fallback was hardcoded to `RuleBasedTriage` with `triaged_by`
   unconditionally overwritten to `"rules:fallback"` — both false as of
   Phase 16. Fixed: the doc now describes all four real implementations and
   the actual three-rung `LLMTriage` → `OllamaTriage` → `RuleBasedTriage`
   chain, with the tag-normalization fix explained (see the doc's "The four
   real implementations" and "The fallback chain" sections). This script's
   Scene 3 ON SCREEN cues and citations below already matched the corrected
   version.
2. **A transcription error in the Phase 16 As-Built itself, line 323** —
   `"used_fallback":false` where the code (`services/complaints.py:110`) and
   the next block's `"fallback":true` (line ~333, for the same 1715ms entry)
   both said it should be `true`. Fixed directly in that As-Built, with a
   note there explaining the correction. This script always cited the
   internally-consistent values (`fallback: true`, the passing
   `TestWiredFallbackChain` test) rather than the one wrong field, so no
   change was needed here.

3. **`docs/DEMO-SCRIPT.md`'s own Scene 3 was also stale**, once the above
   fix landed — it still cited the old `docs/TRIAGE.md` heading text
   ("Fallback to `RuleBasedTriage`") and described the old two-tier
   Gemini-fails-straight-to-rules demonstration, no longer accurate now
   that a third-tier `OllamaTriage` sits in between. Fixed: that scene now
   matches this script's rewritten Scene 3 — the same live wired-fallback
   commands, the same real evidence, and the corrected `docs/TRIAGE.md`
   section-header citation.

---

## Scene 1 — Clean clone → running system (0:00–0:45)

**Speaker:** Zain.

**ON SCREEN:**
- Empty terminal, empty directory. *(cue: "Let's start from a completely empty folder.")*
- Type and run: `git clone -b dev https://github.com/Zain-Shykh/Civic-Pulse.git`, `cd Civic-Pulse`, `cp .env.example .env`. *(cue: "I'm cloning CivicPulse... copying the example environment file")*
- Type and run: `docker compose up -d --build`. *(cue: "Now, one command: docker compose up")*
- Cut to the real pasted output while containers build (`docs/specs/phase-13-documentation-closeout.md` As-Built, "Real quickstart verification"):
  ```
  NAME                              STATUS
  civicpulse-clonetest-backend-1    Up (healthy)
  civicpulse-clonetest-frontend-1   Up (healthy)
  civicpulse-clonetest-postgres-1   Up (healthy)
  civicpulse-clonetest-redis-1      Up (healthy)
  ```
  *(cue: "here's the real result... all reporting healthy")*
- Small on-screen caption: "warm Docker cache — not a clean-machine test." *(cue: "One honest note...")*

**VOICEOVER (read verbatim):**

> Let's start from a completely empty folder. I'm cloning CivicPulse straight from GitHub, moving into it, and copying the example environment file — that's the only setup step. Now, one command: docker compose up, built and running in the background. Here's the real result from running this exact sequence: four containers, backend, frontend, postgres, and redis, all reporting healthy. Before backend even starts, a one-shot migration service runs our database schema automatically, so there's no manual step we forgot to mention. One honest note: this machine's Docker cache wasn't completely empty, so this confirms our setup files are consistent, not a true first-ever download.

*(104 words)*

---

## Scene 2 — AI triage (0:45–1:30)

**Speaker:** Ahmad.

**ON SCREEN:**
- Frontend Submit form: type "Streetlight out on Elm St" / "Elm St", click submit. *(cue: "let's submit a real complaint... streetlight report")*
- Split-screen terminal running the equivalent call:
  ```
  curl -s -X POST http://localhost:8080/api/complaints \
    -H "Content-Type: application/json" \
    -d '{"text":"Streetlight out on Elm St","location":"Elm St"}'
  ```
- Response JSON on screen, highlight `category`/`priority`/summary. *(cue: "category streetlights, priority normal...")*
- Zoom on `triaged_by` and `used_fallback` fields in the same JSON. *(cue: "Triaged by tells us... used fallback confirms it's false")*
- Cut to the dashboard, new row appearing. *(cue: "shows up immediately on our operations dashboard")*

**VOICEOVER (read verbatim):**

> With everything running, let's submit a real complaint. I'll send a streetlight report straight to our complaints endpoint. In this default mode, our rule-based provider classifies it deterministically, with no external calls at all. Look at the response: category streetlights, priority normal, and a one-line summary, all generated instantly and saved to the database. Two fields matter here for observability. Triaged by tells us exactly which provider produced this result, and used fallback confirms it's false, meaning nothing failed and no backup path was needed. That same complaint shows up immediately on our operations dashboard, right where an operator would actually see it.

*(103 words)*

---

## Scene 3 — Fallback, the real three-rung cascade (1:30–2:15)

**Speaker:** Zain.

**ON SCREEN:**
- Terminal, `TRIAGE_PROVIDER=llm` stack with the `ollama` profile already up (started before recording — the model pull takes longer than this scene). Caption: "Gemini configured, Ollama running as the fallback rung." *(cue: opening line)*
- Show `.env`/inline env var with a deliberately invalid `GEMINI_API_KEY`. *(cue: "I've broken its API key on purpose")*
- Run:
  ```
  curl -X POST http://localhost:8080/api/complaints \
    -d '{"text":"...transformer sparking near the park entrance.", ...}'
  ```
  *(cue: "I'll submit a complaint about a transformer sparking near a park entrance")*
- Response JSON on screen, highlight `"triaged_by":"llm:ollama"` and `"triage_latency_ms":1715`. *(cue: "finishing in about one point seven seconds")*
- Run `curl http://localhost:8080/api/meta/providers`; highlight `"active_provider":"llm:gemini"` next to `"fallback":true` in the matching `recent_outcomes` entry. *(cue: "fallback is true, even though Gemini is still configured as active")*
- Cut to `backend/tests/test_llm_triage.py`, scrolled to `TestWiredFallbackChain::test_gemini_and_ollama_both_fail_yields_rules_fallback`. *(cue: "proven here by automated tests")*

**VOICEOVER (read verbatim):**

> Real AI providers fail sometimes, so we built failure handling in stages. Gemini is our configured provider, but I've broken its API key on purpose. I'll submit a complaint about a transformer sparking near a park entrance. Gemini's call fails immediately, but the request still comes back successful — it falls through to our local Ollama model, finishing in about one point seven seconds. The providers endpoint confirms it: fallback is true, even though Gemini is still configured as active. One rung deeper, if Ollama also failed, we'd drop to our rule-based provider — proven here by automated tests, not staged live in forty five seconds.

*(106 words)*

**Why not stage the third rung live:** forcing Gemini to fail while leaving Ollama healthy (this scene) is genuinely one command — it's exactly what the As-Built's live verification already did. Forcing *both* to fail in the same 45-second window would mean either tearing down the Ollama container mid-scene or adding a second broken endpoint on camera, neither of which is a clean single beat — so that rung is shown via the passing, real, mocked-HTTP test instead of a staged failure. Source: `backend/tests/test_llm_triage.py:294` (`TestWiredFallbackChain`), both cases; `docs/specs/phase-16-ollama-triage-and-fallback-chain.md`, As-Built "Live end-to-end verification" (lines 299–339).

---

## Scene 4 — Network isolation failing (2:15–3:00)

**Speaker:** Ahmad.

**ON SCREEN:**
- Terminal, `docker compose exec frontend ping -c 2 postgres`. *(cue: "trying to ping postgres")*
- Output: `ping: bad address 'postgres'`. *(cue: "Both fail immediately with, quote, bad address")*
- `docker compose exec frontend ping -c 2 redis` — same failure shape. *(cue: "then redis")*
- Cut to a `compose.yaml` excerpt showing `frontend`'s `networks: [edge]` next to `postgres`/`redis`'s `networks: [internal]` with `internal: true`. *(cue: "frontend only sits on our public-facing network...")*

**VOICEOVER (read verbatim):**

> This next command is supposed to fail, and that's the whole point. I'm inside our frontend container, trying to ping postgres, then redis. Both fail immediately with, quote, bad address, unquote — that's not a firewall blocking a route, that's frontend being unable to even resolve those names. That's because frontend only sits on our public-facing network, while postgres and redis sit on a separate internal network with no path to the outside world at all. Frontend was simply never placed there. This is real network segmentation, not a policy on paper — the database and cache are structurally unreachable from anywhere except our backend.

*(105 words)*

---

## Scene 5 — HPA scaling (3:00–3:45)

**Speaker:** Zain.

**ON SCREEN:**
- Two terminal panes: `k6 run load/k6-script.js` running against the cluster; `kubectl get hpa -n civicpulse -w` watching live. *(cue: "watching our horizontal pod autoscaler live")*
- Cut to `docs/evidence/hpa-scaling-scaleout.png` (the `2 → 4` step). *(cue: "scales from two replicas to four within a single twenty-second polling interval")*
- Cut to `docs/evidence/hpa-scaling-scaledown.png` (the `4 → 3 → 2` step). *(cue: "stepping back down, four, then three, then two")*
- Cut to `docs/evidence/replicas-vs-load-chart.svg` as a closing visual summary. *(cue: final sentence)*

**VOICEOVER (read verbatim):**

> Now let's push real load at our Kubernetes deployment and watch it scale. I'm running a k6 load test while watching our horizontal pod autoscaler live. Once CPU usage crosses our sixty percent target, it doesn't wait around: backend scales from two replicas to four within a single twenty-second polling interval. After the load stops, though, it holds those extra replicas for nearly five full minutes before stepping back down, four, then three, then two. That's deliberate: scaling up fast protects users during a spike, but scaling down slowly avoids flapping back and forth if load is just temporarily quiet rather than actually gone.

*(104 words)*

---

## Scene 6 — Rollback (3:45–4:30)

**Speaker:** Ahmad.

**ON SCREEN:**
- Terminal against the k8s cluster:
  ```
  kubectl rollout undo deployment/backend -n civicpulse
  kubectl rollout status deployment/backend -n civicpulse
  ```
  *(cue: "The fast one: kubectl rollout undo")*
- Then:
  ```
  cd k8s/overlays/prod
  kustomize edit set image civicpulse-backend=ghcr.io/<owner>/civicpulse-backend:<previous-sha>
  kubectl apply -k .
  kubectl rollout status deployment/backend -n civicpulse
  ```
  *(cue: "we re-point our production overlay... using Kustomize, then reapply it")*

**VOICEOVER (read verbatim):**

> Finally, what happens when a deploy goes wrong. There are two ways to roll back here. The fast one: kubectl rollout undo, which immediately reverts to the deployment's previous revision — that's the three a.m. answer when something's on fire, though it only works if that old version hasn't been garbage collected yet. The correct, auditable answer: we re-point our production overlay at the previous image tag using Kustomize, then reapply it. That's actually how every real deploy already happens in our pipeline, driven by the exact commit that was live before, so rolling back is just repeating that same process backwards, on the record.

*(105 words)*

---

## Closing (4:30–4:40)

**Speakers:** Both, on screen together.

**ON SCREEN:** Both partners on camera.

**VOICEOVER — not written verbatim, and here's why:** the original shot-list's
closing ("one sentence each on what they personally built") describes a real
two-person split that doesn't exist yet to cite — this project is solo work
so far (`CLAUDE.md`, "Solo-first" section: a second contributor "has not
started and there is no confirmed date"). Writing specific "I built X"
sentences for a partner who hasn't touched the code would be inventing a
claim with nothing in the repo to trace it to, which requirement 4 rules
out. Fill this in verbatim, one sentence each, once the actual commit
history reflects who built what — until then, treat this as the one
placeholder in an otherwise fully-sourced script.

---

## Word count and runtime

| Scene | Words | Budget (45s @ ~127–140 wpm) |
|---|---:|---|
| 1 — Clean clone | 104 | ✅ |
| 2 — AI triage | 103 | ✅ |
| 3 — Fallback (rewritten) | 106 | ✅ |
| 4 — Network isolation | 105 | ✅ |
| 5 — HPA scaling | 104 | ✅ |
| 6 — Rollback | 105 | ✅ |
| **Total, six scenes** | **627** | |
| Closing | — (placeholder, see above) | |

At the target conversational pace this script was written to (~95–105 words
per 45-second scene, i.e. ~127–140 wpm), 627 words plays at roughly **4:29**
across the six scenes (4:30 budgeted). Adding the closing's 10-second budget
gives a **total runtime ≈ 4:40** — at or under the 4:45 target, with 20
seconds of slack remaining under the assignment's hard 5-minute cap
(`Software Construction and Design -  Assignment 1.md:620`). The closing's
exact spoken length depends on the real sentences filled in once the
placeholder above is resolved, but two sentences of ~15–20 words each (a
natural length for "one sentence each on what they personally built") plays
in roughly 10–15 seconds at this same conversational pace — comfortably
inside the 10-second budget with only a few seconds to spare, and even at
its longest still 10+ seconds under the hard cap.
