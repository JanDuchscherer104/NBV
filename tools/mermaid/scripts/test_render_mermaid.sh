#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
temp_root="$(mktemp -d)"
trap 'rm -rf "$temp_root"' EXIT

wrapper="$temp_root/tools/mermaid/scripts/render_mermaid.sh"
mkdir -p "$(dirname "$wrapper")" "$temp_root/tools/mermaid/node_modules/.bin"
cp "$repo_root/tools/mermaid/scripts/render_mermaid.sh" "$wrapper"
chmod +x "$wrapper"
touch "$temp_root/diagram.mmd"

cat > "$temp_root/tools/mermaid/node_modules/.bin/mmdc" <<'EOF'
#!/usr/bin/env bash
printf 'repository-local' > "$TEST_MARKER"
EOF
chmod +x "$temp_root/tools/mermaid/node_modules/.bin/mmdc"

cat > "$temp_root/environment-mmdc" <<'EOF'
#!/usr/bin/env bash
printf 'environment' > "$TEST_MARKER"
EOF
chmod +x "$temp_root/environment-mmdc"

marker="$temp_root/selected-cli"
TEST_MARKER="$marker" MERMAID_CLI="$temp_root/environment-mmdc" \
  "$wrapper" "$temp_root/diagram.mmd" "$temp_root/out.svg"
[[ "$(<"$marker")" == "repository-local" ]]

set +e
"$wrapper" "$temp_root/diagram.mmd" --scale >"$temp_root/stdout" 2>"$temp_root/stderr"
status=$?
set -e
[[ $status -eq 2 ]]
rg --fixed-strings -- '--scale requires a value' "$temp_root/stderr"
