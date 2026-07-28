#!/usr/bin/env bash
# Fast 0/1 health probe for the litkg knowledge graph. Used by skills with
# KG-only verification to decide whether to fall back to local discovery.
# Exit 0 = healthy, 1 = degraded (with reason on stderr). Never blocks.
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo_root"

litkg_dir=".agents/external/litkg-rs"
config=".configs/infrastructure/litkg.toml"

if [ ! -f "$config" ]; then
    echo "kg-status: missing $config" >&2
    exit 1
fi
if [ ! -d "$litkg_dir" ]; then
    echo "kg-status: missing $litkg_dir submodule" >&2
    exit 1
fi
if [ ! -f "$litkg_dir/Cargo.toml" ]; then
    echo "kg-status: $litkg_dir submodule not initialized (run: git submodule update --init)" >&2
    exit 1
fi
if ! command -v cargo >/dev/null 2>&1; then
    echo "kg-status: cargo not on PATH" >&2
    exit 1
fi

echo "kg-status: ok"
exit 0
