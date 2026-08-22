#!/usr/bin/env bash
# Informational, path-aware debrief nudge. File counts tune auto emission only;
# the evidence-based capture contract decides eligibility. This never blocks.
set -euo pipefail

threshold=${DEBRIEF_NUDGE_THRESHOLD:-6}
override=${DEBRIEF_NUDGE_ELIGIBLE:-auto}
if ! [[ ${threshold} =~ ^[0-9]+$ ]]; then
    echo "invalid DEBRIEF_NUDGE_THRESHOLD: ${threshold}" >&2
    exit 0
fi
if [[ ${override} != auto && ${override} != true && ${override} != false ]]; then
    echo "invalid DEBRIEF_NUDGE_ELIGIBLE: ${override}" >&2
    exit 0
fi

repo_root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "${repo_root}"
today_iso=$(date +%Y-%m-%d)
history_dir=".agents/memory/history/${today_iso:0:4}/${today_iso:5:2}"
thread=${CODEX_THREAD_ID:-}
if [[ -n ${thread} && ! ${thread} =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
    echo "invalid CODEX_THREAD_ID; debrief nudge remains informational" >&2
    exit 0
fi

if [[ ${override} == false ]]; then
    exit 0
fi

meaningful_count=0
meaningful_paths=()
while IFS= read -r line; do
    path=${line:3}
    [[ -z ${path} ]] && continue
    case "${path}" in
        .agents/memory/history/*|.agents/memory/index/*|.omx/*|.codex/*)
            continue ;;
    esac
    case "${path}" in
        AGENTS.md|Makefile|SETUP.md|README.md|scripts/*|.agents/*|.github/*|aria_nbv/*|docs/*)
            meaningful_count=$((meaningful_count + 1))
            meaningful_paths+=( "${path}" ) ;;
    esac
done < <(git status --porcelain=v1 2>/dev/null)

if [[ ${override} != true && ${meaningful_count} -lt ${threshold} ]]; then
    exit 0
fi

today_records=( "${history_dir}"/${today_iso}_*.md )
if [[ -n ${thread} ]]; then
    for record in "${today_records[@]}"; do
        [[ -f "${record}" ]] || continue
        if grep -q -F "codex_thread: codex://threads/${thread}" "${record}"; then
            exit 0
        fi
    done
elif [[ ${meaningful_count} -gt 0 ]]; then
    for record in "${today_records[@]}"; do
        [[ -f "${record}" ]] || continue
        touched_block=$(sed -n '/^touched_owner_paths:/,/^[A-Za-z0-9_-][A-Za-z0-9_-]*:/p' "${record}")
        covers_all=true
        for path in "${meaningful_paths[@]}"; do
            if ! grep -Fqx "  - ${path}" <<<"${touched_block}"; then
                covers_all=false
                break
            fi
        done
        if [[ ${covers_all} == true ]]; then
            exit 0
        fi
    done
fi

thread_arg=
if [[ -n ${thread} ]]; then
    thread_arg=" CODEX_THREAD_ID='${thread}'"
fi
cat >&2 <<NUDGE
[debrief-nudge] no matching dated debrief was found under ${history_dir}/.

If this work contains reusable evidence, a durable decision, a failed approach,
consequential verification, or canonical-owner impact, run:

    make new-debrief TITLE='<short title>'${thread_arg}

MemPalace and the derived index are optional/navigation-only surfaces.
NUDGE
exit 0
