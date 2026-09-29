# syntax=docker/dockerfile:1

# The official ollama/ollama:0.34.4 Docker Hub image is ~9.3GB on disk
# because the upstream Linux release tarball bundles CUDA v12 and v13
# runners unconditionally (confirmed by downloading the real pinned
# ollama-linux-amd64.tar.zst: ~2.1GB extracted, of which lib/ollama/cuda_v12
# + cuda_v13 + vulkan alone are ~2.05GB) — the official install script only
# skips this for the *systemd* install path when it doesn't detect a GPU at
# install time, not for the Docker image, which must ship every backend
# since it can't know the eventual host's hardware. This project's design
# is deliberately CPU-only (qwen2.5:0.5b, chosen for no-GPU laptop
# performance — docs/specs/phase-16-ollama-triage-and-fallback-chain.md),
# so those runner directories are stripped in this same build stage,
# before they ever reach a layer that ships. Real resulting image: ~211MB,
# vs ~9.3GB upstream (confirmed, not estimated).
FROM debian:bookworm-slim AS fetch
ARG OLLAMA_VERSION=0.34.4
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl zstd \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /extract
RUN curl -fsSL -o ollama.tar.zst \
      "https://github.com/ollama/ollama/releases/download/v${OLLAMA_VERSION}/ollama-linux-amd64.tar.zst" \
    && tar --zstd -xf ollama.tar.zst \
    && rm -rf lib/ollama/cuda_v12 lib/ollama/cuda_v13 lib/ollama/vulkan ollama.tar.zst

FROM debian:bookworm-slim AS runtime
ARG OLLAMA_VERSION=0.34.4
LABEL org.opencontainers.image.version=${OLLAMA_VERSION}

# ca-certificates: TLS to registry.ollama.ai for `ollama pull`. Everything
# else the binary needs (libstdc++, libgomp, ggml/CPU-runner .so files) is
# self-contained under lib/ollama, confirmed via `ldd` against a bare
# debian:bookworm-slim base — no other system packages required.
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system ollama \
    && useradd --system --gid ollama --home-dir /usr/share/ollama --create-home ollama \
    # Pre-created (not left for Compose's volume-mount auto-creation, which
    # defaults new mount points to root:root) so the ollama_models volume
    # mounted here is writable by the non-root ollama user from first boot.
    && mkdir -p /usr/share/ollama/.ollama \
    && chown -R ollama:ollama /usr/share/ollama

# Same /usr layout the official manual-install docs use (`tar x -C /usr`),
# so the binary finds its lib/ollama companion directory the same way a
# real install would, not a guessed path.
COPY --from=fetch /extract/bin/ollama /usr/bin/ollama
COPY --from=fetch /extract/lib/ollama /usr/lib/ollama
COPY --chmod=755 pull-model.sh /usr/local/bin/pull-model.sh

USER ollama
# $HOME/.ollama/models is upstream's own default model directory on Linux
# (docs/faq.mdx, "Where are models stored?") — matched here rather than
# invented, so no OLLAMA_MODELS override is needed.
ENV HOME=/usr/share/ollama
# Without this, the server defaults to binding 127.0.0.1 only (confirmed by
# running it) — unreachable from any other container on the same Docker
# network, including ollama-pull. The official Docker Hub image sets this
# same override for the same reason.
ENV OLLAMA_HOST=0.0.0.0:11434
EXPOSE 11434

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=10 \
    CMD ["ollama", "list"]

ENTRYPOINT ["ollama"]
CMD ["serve"]
