# Phase NN: <name>
Status: <not started | in progress | implemented, pending review | done>
Depends on: <phase(s)>
Reads first: <which docs/*.md files are authoritative for this phase>

## Goal
One paragraph.

## Deliverables
Explicit file list — nothing built outside this list without flagging it.

## Non-goals
What this phase must NOT include yet (this has been one of the most useful
lines in every spec so far — keep it mandatory).

## Plan
Mandatory for every phase, no complexity exceptions — depth scales with
the phase's actual complexity, existence doesn't. Before writing any code,
write here: the files to be touched, in the order they'll be touched;
the key technical choices to be made and why; anything you're uncertain
about. A few bullets is enough for mechanical work; go deeper where real
technical decisions exist. This section is committed on its own and the
human approves it before implementation starts — never skipped, never
implied by the Spec alone.

## Verification required
Exact commands to run, real output required in the report — no summaries.

## Ambiguity handling
If anything here conflicts with CONTRACTS.md or is underspecified, stop and
ask — do not silently resolve.

## As-Built
Filled in after the phase completes: real verification output (pasted,
not summarized), and any deviation from the Plan or the Spec above, with
why.
