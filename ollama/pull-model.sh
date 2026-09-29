#!/bin/sh
# Runs its own throwaway local `ollama serve` against the same shared
# ollama_models volume the real, long-running `ollama` service reads from,
# pulls the requested model into it, then exits — never talks to that other
# service over the network at all.
#
# Why not just point OLLAMA_HOST at the real service instead (simpler,
# no local server needed): confirmed empirically that this container would
# then need to join the `internal` network to reach it, and the real
# `ollama` binary's Go DNS resolver reliably fails external hostname
# lookups (registry.ollama.ai) whenever the container is also a member of
# an `internal: true` Docker network — reproduced consistently (5/5 and
# more) against this exact real Compose stack, and reproduced again, in
# isolation, with two throwaway plain bridge networks vs. one throwaway
# `internal: true` + one plain bridge network: identical container, image,
# and command, the only variable being the `internal: true` flag. glibc-
# based resolution (getent, and this project's own Python-based backend/
# Gemini calls) is unaffected either way — this is specific to Go binaries
# using Go's own resolver, and specific to Docker's embedded DNS proxy's
# handling of `internal: true` networks. Writing straight into the shared
# volume sidesteps the bug entirely rather than working around it, and
# also means this container never needs `internal` network membership,
# so it no longer bridges edge/internal the way the first design did.
set -eu

ollama serve &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true' EXIT

for _ in $(seq 1 30); do
    ollama list >/dev/null 2>&1 && break
    sleep 1
done

ollama pull "$1"
