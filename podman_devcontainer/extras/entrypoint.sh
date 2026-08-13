#!/bin/bash
# entrypoint.sh — runs as the "coder" user inside the workspace pod.
#
# 1. Starts the rootless Podman socket in the background.
# 2. Waits up to 30 s for the socket file to appear.
# 3. exec's whatever is passed as CMD (the Coder agent bootstrap script).
#
# Because we exec at the end, the Coder agent becomes PID 1's child and
# receives signals normally.

set -euo pipefail

# ── Podman socket ──────────────────────────────────────────────────────────────
PODMAN_SOCK="/tmp/podman/podman.sock"

echo "[entrypoint] Starting Podman socket at ${PODMAN_SOCK}..."
mkdir -p "$(dirname "${PODMAN_SOCK}")"

# --time=0 keeps the service alive indefinitely (no idle timeout)
podman system service --time=0 "unix://${PODMAN_SOCK}" &

# ── Wait for socket ────────────────────────────────────────────────────────────
echo "[entrypoint] Waiting for Podman socket..."
timeout 30 bash -c \
  "until test -S \"${PODMAN_SOCK}\"; do sleep 0.5; done" \
  || { echo "[entrypoint] ERROR: Podman socket did not appear within 30 s"; exit 1; }

echo "[entrypoint] Podman socket ready."

# Export so child processes (e.g. docker-compatible CLIs) can find it
export DOCKER_HOST="unix://${PODMAN_SOCK}"

# ── Hand off to Coder agent (or whatever CMD was set) ─────────────────────────
exec "$@"
