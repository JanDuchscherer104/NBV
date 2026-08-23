#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: render_png.sh -i <input.typ> [-o <out_dir>] [-p <ppi>] [--pages <ranges>] [--root <dir>]

Environment:
  TYPST_BIN     Typst executable override (default: typst)

Options:
  -i, --input     Path to .typ file (required)
  -o, --out       Output directory (default: ./out)
  -p, --ppi       Pixels per inch (default: 300)
      --pages     Page ranges (e.g., "1", "2,3,7-9,11-")
      --root      Typst project root passed to `typst compile --root`
  -h, --help      Show this help

Examples:
  .agents/skills/typst-authoring/scripts/render_png.sh -i figure.typ
  .agents/skills/typst-authoring/scripts/render_png.sh -i docs/typst/thesis/main.typ -o /tmp/renders --root docs --ppi 600 --pages 1
  .agents/skills/typst-authoring/scripts/render_png.sh -i .agents/skills/typst-authoring/assets/fixtures/attachments-and-operators.typ -o /tmp/fixtures --root . --pages 1
EOF
}

input=""
out_dir="./out"
ppi="300"
pages=""
root=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -i|--input)
      input="$2"
      shift 2
      ;;
    -o|--out)
      out_dir="$2"
      shift 2
      ;;
    -p|--ppi)
      ppi="$2"
      shift 2
      ;;
    --pages)
      pages="$2"
      shift 2
      ;;
    --root)
      root="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$input" ]]; then
  echo "Missing required --input" >&2
  usage
  exit 1
fi

typst_bin="${TYPST_BIN:-typst}"
if ! command -v "$typst_bin" >/dev/null 2>&1 && [[ ! -x "$typst_bin" ]]; then
  echo "Typst CLI not found: $typst_bin" >&2
  exit 127
fi

mkdir -p "$out_dir"

output_template="${out_dir}/{0p}.png"

args=(compile "$input" "$output_template" --format png --ppi "$ppi")
if [[ -n "$pages" ]]; then
  args+=(--pages "$pages")
fi
if [[ -n "$root" ]]; then
  args+=(--root "$root")
fi

printf 'Running:' >&2
printf ' %q' "$typst_bin" "${args[@]}" >&2
printf '\n' >&2

"$typst_bin" "${args[@]}"
