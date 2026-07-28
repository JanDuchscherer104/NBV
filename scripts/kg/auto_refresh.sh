#!/usr/bin/env bash
# Background-safe KG refresh — bucket-aware dispatch.
#
# Wired into the Claude `Stop` hook, Codex `Stop` hook, and Gemini `SessionEnd`
# hook (see .claude/settings.json, .codex/hooks.json, .gemini/settings.json).
# Never blocks the calling session, never errors out, never produces stdout/
# stderr the user has to read. All state goes to .agents/kg/.refresh.log.
#
# Detects which buckets changed since the last successful refresh and runs
# only the matching narrow targets, in the background:
#
#   backlog bucket — .agents/*.toml
#       → kg-export-neo4j + kg-load-bundle + kg-enrich
#         (rebuilds JSONL bundle, MERGEs into live Neo4j, embeds new nodes)
#   docs bucket    — docs/contents/**, docs/typst/**, docs/references.bib
#       → kg-export-neo4j + kg-load-bundle + kg-enrich
#         (same pipeline; the litkg sources globs cover both)
#   code bucket    — aria_nbv/aria_nbv/**/*.py
#       → kg-refresh-code (rebuilds the CodeGraphContext index in Neo4j)
#         then kg-enrich (embeds new code symbols)
#
# Always runs the cheap `kg-refresh-light` step (refreshes the lightweight
# scaffold context that agents read on session start) whenever ANY bucket is
# dirty.
#
# Skips silently when:
#   - the Mac/remote Ollama endpoint at 127.0.0.1:11434 is not reachable
#     (your `ssh -N -R 11434:127.0.0.1:11434 ubuntu` tunnel is down);
#   - no tracked source in any bucket has been modified since
#     .agents/kg/.last-refresh;
#   - another refresh is already in flight (.agents/kg/.refresh.lock present).
#
# Env knobs:
#   KG_FORCE=1            Skip the Ollama probe + staleness check; always run.
#   KG_NEO4J_AUTO_UP=1    Warm-start `make kg-up` when Neo4j is unreachable.
#   KG_REFRESH_SYNC=1     Run targets in the foreground (default backgrounds).
#                         Useful for testing or post-commit hooks where you
#                         want exit codes.
#
# Manually clear a stale lock:
#   rm .agents/kg/.refresh.lock

set -u

REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$REPO" || exit 0

KG_DIR="$REPO/.agents/kg"
LOG="$KG_DIR/.refresh.log"
STAMP="$KG_DIR/.last-refresh"
LOCK="$KG_DIR/.refresh.lock"
TS="$(date -Iseconds)"
FORCE="${KG_FORCE:-0}"
SYNC="${KG_REFRESH_SYNC:-0}"

mkdir -p "$KG_DIR" 2>/dev/null || exit 0

log() {
  echo "$TS $*" >> "$LOG" 2>/dev/null || true
}

# 1) Ollama tunnel reachable? Skip on first failure (don't retry).
if [ "$FORCE" != "1" ]; then
  if ! curl -sSf --max-time 1 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    log "skip: ollama tunnel unreachable at 127.0.0.1:11434"
    exit 0
  fi
fi

# 1a) Optional Neo4j warm-start. Opt-in via KG_NEO4J_AUTO_UP=1.
neo4j_up() {
  curl -sSf --max-time 1 http://127.0.0.1:7474/ >/dev/null 2>&1
}
if [ "${KG_NEO4J_AUTO_UP:-0}" = "1" ]; then
  if ! neo4j_up; then
    log "neo4j down and KG_NEO4J_AUTO_UP=1 set; attempting make kg-up"
    if command -v docker >/dev/null 2>&1; then
      ( nohup make kg-up >> "$LOG" 2>&1 & disown 2>/dev/null || true )
      log "kg-up dispatched in background; vector search available after warm-up"
    else
      log "skip: docker not on PATH; cannot warm-start Neo4j"
    fi
  fi
fi

# 2) Bucket detection. find ... -newer "$STAMP" only fires when the stamp
# exists; the first run (no stamp) treats every bucket as dirty.
bucket_dirty() {
  local stamp="$1"; shift
  if [ ! -f "$stamp" ]; then
    echo 1
    return
  fi
  if find "$@" -type f -newer "$stamp" 2>/dev/null | head -1 | grep -q .; then
    echo 1
  fi
}

memory_paths=(
  .agents/issues.toml
  .agents/todos.toml
  .agents/refactors.toml
  .agents/resolved.toml
)
docs_paths=(
  docs/contents
  docs/typst
  docs/references.bib
)
code_paths=(
  aria_nbv/aria_nbv
)

memory_dirty=$(bucket_dirty "$STAMP" "${memory_paths[@]}" 2>/dev/null)
docs_dirty=$(bucket_dirty "$STAMP" "${docs_paths[@]}" 2>/dev/null)
code_dirty=$(bucket_dirty "$STAMP" "${code_paths[@]}" 2>/dev/null)

if [ "$FORCE" != "1" ] && [ -z "$memory_dirty$docs_dirty$code_dirty" ]; then
  log "skip: no bucket dirty since last refresh"
  exit 0
fi

# 3) Lock — abort if a previous refresh is still running.
if ! ( set -o noclobber; echo "$$" > "$LOCK" ) 2>/dev/null; then
  existing=$(cat "$LOCK" 2>/dev/null || echo "?")
  log "skip: refresh already running (pid $existing); leave it alone"
  exit 0
fi

# 4) Run the dispatched targets. Background by default; sync when requested.
dispatch() {
  local buckets=""
  [ -n "$memory_dirty" ] && buckets="${buckets}memory "
  [ -n "$docs_dirty" ]   && buckets="${buckets}docs "
  [ -n "$code_dirty" ]   && buckets="${buckets}code "
  log "start: dispatch buckets=[${buckets% }] sync=$SYNC"

  # Cheap context refresh — always run when anything dirty.
  make kg-refresh-light >> "$LOG" 2>&1 || log "warn: kg-refresh-light non-zero"

  # Code-symbol bucket.
  if [ -n "$code_dirty" ]; then
    make kg-refresh-code >> "$LOG" 2>&1 || log "warn: kg-refresh-code non-zero"
  fi

  # Memory/docs buckets share the ingestion + embedding pipeline. Skip when
  # Neo4j is down (the load step depends on it).
  if [ -n "$memory_dirty$docs_dirty" ]; then
    make kg-export-neo4j >> "$LOG" 2>&1 || log "warn: kg-export-neo4j non-zero"
    if neo4j_up; then
      make kg-load-bundle >> "$LOG" 2>&1 || log "warn: kg-load-bundle non-zero"
    else
      log "skip: neo4j down; bundle export ready but not loaded"
    fi
  fi

  # Embedding pass — runs when anything dirty AND Neo4j is up.
  # enrich_embeddings.py is idempotent (skips nodes that already have
  # kg_embedding), so this is cheap on no-op.
  if neo4j_up; then
    make kg-enrich >> "$LOG" 2>&1 || log "warn: kg-enrich non-zero"
  else
    log "skip: neo4j down; embeddings will lag until next refresh"
  fi

  touch "$STAMP"
  # Opportunistic health snapshot. --soft keeps the hook from failing on red;
  # the JSON payload lands in the refresh log alongside the make output.
  log "doctor snapshot:"
  python3 scripts/kg/doctor.py --soft --format json >> "$LOG" 2>&1 || true
  log "done: dispatch buckets=[${buckets% }] complete"
}

if [ "$SYNC" = "1" ]; then
  # Foreground: caller wants the exit code (e.g. git post-commit script).
  trap 'rm -f "$LOCK"' EXIT
  dispatch
  exit 0
else
  # Background: caller is a session-end hook and must not block.
  (
    trap 'rm -f "$LOCK"' EXIT
    dispatch
  ) </dev/null >/dev/null 2>&1 &
  disown 2>/dev/null || true
  exit 0
fi
