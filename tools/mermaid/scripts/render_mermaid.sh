#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <diagram.mmd> [output.svg|output.png|output.pdf] [--scale <n>]" >&2
  exit 2
fi

input="$1"
shift
output="${input%.mmd}.svg"
if [[ $# -gt 0 && "$1" != --* ]]; then
  output="$1"
  shift
fi

scale=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --scale)
      if [[ $# -lt 2 || "$2" == --* ]]; then
        echo "--scale requires a value" >&2
        exit 2
      fi
      scale="$2"
      shift 2
      ;;
    *)
      echo "unknown option: $1" >&2
      exit 2
      ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
local_mmdc="$repo_root/tools/mermaid/node_modules/.bin/mmdc"

if [[ -x "$local_mmdc" ]]; then
  mmdc="$local_mmdc"
elif [[ -n "${MERMAID_CLI:-}" ]]; then
  mmdc="$MERMAID_CLI"
elif mmdc="$(command -v mmdc 2>/dev/null)"; then
  :
else
  echo "ERROR: no Mermaid CLI found." >&2
  echo "Expected a repository-local tool at $local_mmdc, MERMAID_CLI, or mmdc on PATH." >&2
  echo "For unpublished figures, use a local installation; this wrapper never downloads or uses an online renderer." >&2
  exit 127
fi

mkdir -p "$(dirname "$output")"
cmd=("$mmdc" -i "$input" -o "$output" -b white -t default)
if [[ -n "$scale" ]]; then
  cmd+=(-s "$scale")
fi
"${cmd[@]}"
printf 'Rendered %s -> %s\n' "$input" "$output"
