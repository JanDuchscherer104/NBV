#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 1 ]]; then
  echo "usage: $0 <diagram.mmd> [output.svg|output.png|output.pdf] [--scale <n>] [--puppeteer-config <file>]" >&2
  exit 2
fi
input="$1"; shift
output="${input%.mmd}.svg"
if [[ $# -gt 0 && "$1" != --* ]]; then output="$1"; shift; fi
scale=""
puppeteer_config=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --scale|--puppeteer-config)
      if [[ $# -lt 2 || "$2" == --* ]]; then echo "$1 requires a value" >&2; exit 2; fi
      if [[ "$1" == --scale ]]; then scale="$2"; else puppeteer_config="$2"; fi
      shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
local_mmdc="$repo_root/tools/mermaid/node_modules/.bin/mmdc"
if [[ -x "$local_mmdc" ]]; then mmdc="$local_mmdc"
elif [[ -n "${MERMAID_CLI:-}" ]]; then mmdc="$MERMAID_CLI"
elif mmdc="$(command -v mmdc 2>/dev/null)"; then :
else
  echo "ERROR: no Mermaid CLI found." >&2
  echo "Expected $local_mmdc, MERMAID_CLI, or mmdc on PATH. No automatic download." >&2
  exit 127
fi
mkdir -p "$(dirname "$output")"
cmd=("$mmdc" -i "$input" -o "$output" -b white -t default)
if [[ -n "$scale" ]]; then cmd+=(-s "$scale"); fi
if [[ -n "$puppeteer_config" ]]; then cmd+=(-p "$puppeteer_config"); fi
"${cmd[@]}"
printf 'Rendered %s -> %s\n' "$input" "$output"
