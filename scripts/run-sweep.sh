#!/usr/bin/env bash
# Cron-friendly sweep (+ optional Discord post when new items exist).
# On failure, ALWAYS prints SWEEP BLOCKED / error text — do not discard stdout.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

set -a
# shellcheck disable=SC1091
[ -f .env ] && . ./.env
set +a

# Capture both stdout and stderr so blockers are never lost.
set +e
OUT=$(python3 sweep.py --quiet 2>&1)
RC=$?
set -e

if [ "$RC" -ne 0 ]; then
  echo "SWEEP FAILED (exit $RC)"
  echo "$OUT"
  exit "$RC"
fi

if [ -n "${OUT}" ]; then
  echo "$OUT"
  if [ "${DISCORD_ENABLED:-0}" = "1" ] || [ -n "${DISCORD_FORUM_CHANNEL_ID:-}" ]; then
    python3 forum_post.py || echo "FORUM POST FAILED"
  fi
fi
