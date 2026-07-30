#!/usr/bin/env bash
# Informational nudge: warn when a session changed many tracked files but did
# not produce a new debrief under .agents/memory/history/YYYY/MM/. Never
# blocks; debrief decisions stay with the human/agent.
#
# Wired into `.codex/hooks.example.json` as an operator-local Stop hook template.
set -euo pipefail

THRESHOLD="${DEBRIEF_NUDGE_THRESHOLD:-6}"

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo_root"

changed_count="$(git status --porcelain 2>/dev/null | grep -Ev '^\?\? ' | wc -l | tr -d ' ')"
if [ "${changed_count:-0}" -lt "$THRESHOLD" ]; then
    exit 0
fi

today_year="$(date +%Y)"
today_month="$(date +%m)"
today_iso="$(date +%Y-%m-%d)"
history_dir=".agents/memory/history/${today_year}/${today_month}"

if [ -d "$history_dir" ] && ls "$history_dir" 2>/dev/null | grep -q "^${today_iso}_"; then
    exit 0
fi

cat >&2 <<NUDGE
[debrief-nudge] session touched ${changed_count} tracked files but no new debrief
under ${history_dir}/${today_iso}_*.md was found.

If this work was non-trivial, scaffold one:

    make new-debrief TITLE='<short title>'

If the work did not change current truth, say so explicitly in the debrief
instead of relying on chat history. Set DEBRIEF_NUDGE_THRESHOLD to tune.
NUDGE
exit 0
