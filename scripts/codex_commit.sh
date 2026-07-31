#!/bin/sh
set -eu

if [ -z "${CODEX_THREAD_ID:-}" ]; then
  echo "CODEX_THREAD_ID is required for scripts/codex_commit.sh" >&2
  exit 2
fi
if [ -z "${CODEX_TRANSCRIPT_SCOPE_START:-}" ]; then
  echo "CODEX_TRANSCRIPT_SCOPE_START is required for scripts/codex_commit.sh" >&2
  exit 2
fi

ROOT=$(git rev-parse --show-toplevel)
MODE=$(python3 "$ROOT/scripts/codex_transcript_provenance.py" validate-invocation -- "$@")
NONCE=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
export ARIA_CODEX_COMMIT=1
export ARIA_CODEX_THREAD_ID="$CODEX_THREAD_ID"
export ARIA_CODEX_SCOPE_START="$CODEX_TRANSCRIPT_SCOPE_START"
export ARIA_CODEX_AMEND=0
[ "$MODE" = "amend" ] && export ARIA_CODEX_AMEND=1
export ARIA_CODEX_INVOCATION_NONCE="$NONCE"

cleanup_state() {
  python3 "$ROOT/scripts/codex_transcript_provenance.py" clear-state \
    --repo "$ROOT" --invocation-nonce "$NONCE" "$@"
}
trap 'cleanup_state --cleanup-artifact >/dev/null 2>&1 || true; exit 130' HUP INT TERM
status=0
git commit "$@" || status=$?
trap - HUP INT TERM
cleanup=
[ "$status" -ne 0 ] && cleanup=--cleanup-artifact
cleanup_state $cleanup || {
  echo "failed to clear Codex commit invocation state" >&2
  exit 1
}
exit "$status"
