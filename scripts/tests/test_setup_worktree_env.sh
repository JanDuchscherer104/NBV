#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/aria-worktree-env.XXXXXX")"
trap 'rm -rf "${SANDBOX}"' EXIT

SHARED_ROOT="${SANDBOX}/shared"
WORKTREE_ROOT="${SANDBOX}/worktree"
SECOND_WORKTREE_ROOT="${SANDBOX}/second-worktree"
COLLISION_ROOT="${SANDBOX}/collision-worktree"
FAKE_BIN="${SANDBOX}/bin"

mkdir -p \
  "${SHARED_ROOT}/aria_nbv/.venv/bin" \
  "${SHARED_ROOT}/.data/ase_efm" \
  "${SHARED_ROOT}/.data/offline_cache" \
  "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic" \
  "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic-deep" \
  "${SHARED_ROOT}/docs/literature/pdf" \
  "${SHARED_ROOT}/scripts" "${FAKE_BIN}"
cp "${REPO_ROOT}/scripts/setup_worktree_env.sh" "${SHARED_ROOT}/scripts/"
cp "${REPO_ROOT}/scripts/graphify_worktree_seed.py" "${SHARED_ROOT}/scripts/"
cp "${REPO_ROOT}/.env.example" "${SHARED_ROOT}/"
touch "${SHARED_ROOT}/aria_nbv/.gitkeep" "${SHARED_ROOT}/docs/literature/.gitkeep"

git -C "${SHARED_ROOT}" init -q
git -C "${SHARED_ROOT}" config user.email test@example.invalid
git -C "${SHARED_ROOT}" config user.name test
git -C "${SHARED_ROOT}" config extensions.worktreeConfig true
git -C "${SHARED_ROOT}" add .
git -C "${SHARED_ROOT}" commit -qm fixture
ln -s "$(command -v python3)" "${SHARED_ROOT}/aria_nbv/.venv/bin/python"
cat >"${SHARED_ROOT}/fake-graphify-python" <<'EOF'
#!/usr/bin/env sh
printf '%s\n' 0.9.31
EOF
chmod +x "${SHARED_ROOT}/fake-graphify-python"
git -C "${SHARED_ROOT}" worktree add -qb seed-child "${WORKTREE_ROOT}"
git -C "${SHARED_ROOT}" worktree add -qb seed-second "${SECOND_WORKTREE_ROOT}"
git -C "${SHARED_ROOT}" worktree add -qb seed-collision "${COLLISION_ROOT}"

# The source seed is deliberately untracked. Graphify output is an ignored,
# derived artifact and setup must nevertheless require a complete valid parent.
mkdir -p "${SHARED_ROOT}/graphify-out" "${SHARED_ROOT}/graphify-input"
cat >"${SHARED_ROOT}/graphify-out/graph.json" <<EOF
{"built_at_commit":"$(git -C "${SHARED_ROOT}" rev-parse HEAD)","nodes":[{"source_file":"graphify-input/index.md"}]}
EOF
cat >"${SHARED_ROOT}/graphify-out/manifest.json" <<'EOF'
{"graphify-input/index.md":{"semantic_hash":"fixture"}}
EOF
printf '%s\n' "${SHARED_ROOT}/fake-graphify-python" >"${SHARED_ROOT}/graphify-out/.graphify_python"
cat >"${SHARED_ROOT}/graphify-input/index.md" <<'EOF'
---
title: fixture
---
# fixture
EOF
# These are explicitly never inherited.
mkdir -p "${SHARED_ROOT}/graphify-out/cache"
printf '{}\n' >"${SHARED_ROOT}/graphify-out/cache/stat-index.json"
printf '{}\n' >"${SHARED_ROOT}/graphify-out/.graphify_detect.json"
printf 'report\n' >"${SHARED_ROOT}/graphify-out/report.md"
mkdir -p "${SHARED_ROOT}/graphify-out/wiki"
printf 'query\n' >"${SHARED_ROOT}/graphify-out/query.json"

cat >"${FAKE_BIN}/readlink" <<'EOF'
#!/usr/bin/env bash
echo "readlink must not be used" >&2
exit 99
EOF
chmod +x "${FAKE_BIN}/readlink"

cat >"${FAKE_BIN}/mamba" <<'EOF'
#!/usr/bin/env bash
echo "mamba must not be used" >&2
exit 98
EOF
chmod +x "${FAKE_BIN}/mamba"

# Preserve d6a's explicit-Git-dir regression: ambient Git discovery reports a
# stale worktree, while setup must still address this child explicitly.
git -C "${WORKTREE_ROOT}" config --worktree core.worktree "${SANDBOX}/stale-worktree"
git -C "${SECOND_WORKTREE_ROOT}" config --worktree core.worktree "${SANDBOX}/stale-second-worktree"
[[ "$(git -C "${WORKTREE_ROOT}" rev-parse --is-inside-work-tree)" == false ]]
[[ "$(git -C "${SECOND_WORKTREE_ROOT}" rev-parse --is-inside-work-tree)" == false ]]

run_setup() {
  ARIA_NBV_SHARED_ROOT="${SHARED_ROOT}" PATH="${FAKE_BIN}:${PATH}" \
    bash "$1/scripts/setup_worktree_env.sh" "${@:2}"
}

if run_setup "${WORKTREE_ROOT}" --check >"${SANDBOX}/fresh.out" 2>"${SANDBOX}/fresh.err"; then
  echo "--check unexpectedly accepted an unseeded worktree" >&2
  exit 1
fi
grep -Fq ".venv is not linked" "${SANDBOX}/fresh.err"
[[ ! -e "${WORKTREE_ROOT}/graphify-out/graph.json" ]]

run_setup "${WORKTREE_ROOT}"
[[ -d "${WORKTREE_ROOT}/.data" ]]
[[ -L "${WORKTREE_ROOT}/.data/ase_efm" ]]
[[ -L "${WORKTREE_ROOT}/.data/offline_cache" ]]
[[ -L "${WORKTREE_ROOT}/docs/literature/pdf" ]]
[[ -L "${WORKTREE_ROOT}/.env" ]]
[[ ! -e "${WORKTREE_ROOT}/.data/graphify-semantic-cache" ]]
[[ ! -L "${WORKTREE_ROOT}/.data/graphify-semantic-cache" ]]
for path in graphify-out/graph.json graphify-out/manifest.json graphify-out/.graphify_python graphify-input/index.md graphify-out/.graphify_root graphify-out/.aria-worktree-seed.json; do
  [[ -f "${WORKTREE_ROOT}/${path}" && ! -L "${WORKTREE_ROOT}/${path}" ]]
done
[[ "$(cat "${WORKTREE_ROOT}/graphify-out/.graphify_root")" == "${WORKTREE_ROOT}" ]]
[[ ! -e "${WORKTREE_ROOT}/graphify-out/cache/stat-index.json" ]]
[[ ! -e "${WORKTREE_ROOT}/graphify-out/.graphify_detect.json" ]]
[[ ! -e "${WORKTREE_ROOT}/graphify-out/report.md" ]]
[[ ! -e "${WORKTREE_ROOT}/graphify-out/wiki" ]]
[[ ! -e "${WORKTREE_ROOT}/graphify-out/query.json" ]]
[[ -L "${WORKTREE_ROOT}/graphify-out/cache/semantic" ]]
[[ -L "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep" ]]

run_setup "${SECOND_WORKTREE_ROOT}"
[[ "$(readlink -f "${SECOND_WORKTREE_ROOT}/graphify-out/cache/semantic")" == "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic" ]]
[[ "$(readlink -f "${SECOND_WORKTREE_ROOT}/graphify-out/cache/semantic-deep")" == "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic-deep" ]]
[[ ! -e "${SECOND_WORKTREE_ROOT}/.data/graphify-semantic-cache" ]]
[[ ! -L "${SECOND_WORKTREE_ROOT}/.data/graphify-semantic-cache" ]]
printf 'cache-hit\n' >"${WORKTREE_ROOT}/graphify-out/cache/semantic/cache-hit.json"
grep -Fqx cache-hit "${SECOND_WORKTREE_ROOT}/graphify-out/cache/semantic/cache-hit.json"
printf '{"built_at_commit":"child","nodes":[{"source_file":"graphify-input/index.md"}]}\n' >"${WORKTREE_ROOT}/graphify-out/graph.json"
grep -Fq 'graphify-input/index.md' "${SHARED_ROOT}/graphify-out/graph.json"
[[ ! -e "${SECOND_WORKTREE_ROOT}/graphify-out/graph.json" || "$(cat "${SECOND_WORKTREE_ROOT}/graphify-out/graph.json")" != "$(cat "${WORKTREE_ROOT}/graphify-out/graph.json")" ]]

# Idempotence never overwrites local mutable graph state; --check is read-only.
before="$(sha256sum "${WORKTREE_ROOT}/graphify-out/graph.json")"
run_setup "${WORKTREE_ROOT}"
[[ "$(sha256sum "${WORKTREE_ROOT}/graphify-out/graph.json")" == "${before}" ]]
run_setup "${WORKTREE_ROOT}" --check
[[ "$(sha256sum "${WORKTREE_ROOT}/graphify-out/graph.json")" == "${before}" ]]

unlink "${WORKTREE_ROOT}/graphify-out/cache/semantic"
ln -s "${SHARED_ROOT}/.data/offline_cache" "${WORKTREE_ROOT}/graphify-out/cache/semantic"
if run_setup "${WORKTREE_ROOT}" >"${SANDBOX}/wrong-semantic.out" 2>"${SANDBOX}/wrong-semantic.err"; then
  echo "setup unexpectedly replaced a wrong semantic cache link" >&2
  exit 1
fi
grep -Fq "graphify-out/cache/semantic points somewhere else" "${SANDBOX}/wrong-semantic.err"
[[ "$(readlink -f "${WORKTREE_ROOT}/graphify-out/cache/semantic")" == "${SHARED_ROOT}/.data/offline_cache" ]]
unlink "${WORKTREE_ROOT}/graphify-out/cache/semantic"
ln -s "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic" "${WORKTREE_ROOT}/graphify-out/cache/semantic"

unlink "${WORKTREE_ROOT}/graphify-out/cache/semantic"
if run_setup "${WORKTREE_ROOT}" --check >"${SANDBOX}/missing-semantic.out" 2>"${SANDBOX}/missing-semantic.err"; then
  echo "--check unexpectedly accepted a missing semantic cache link" >&2
  exit 1
fi
grep -Fq "graphify-out/cache/semantic is not linked" "${SANDBOX}/missing-semantic.err"
ln -s "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic" "${WORKTREE_ROOT}/graphify-out/cache/semantic"

unlink "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep"
mkdir "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep"
touch "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep/keep"
if run_setup "${WORKTREE_ROOT}" >"${SANDBOX}/semantic-collision.out" 2>"${SANDBOX}/semantic-collision.err"; then
  echo "setup unexpectedly replaced a semantic-deep cache collision" >&2
  exit 1
fi
grep -Fq "graphify-out/cache/semantic-deep already exists" "${SANDBOX}/semantic-collision.err"
[[ -f "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep/keep" ]]
rm "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep/keep"
rmdir "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep"
ln -s "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic-deep" "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep"

unlink "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep"
printf 'do-not-overwrite\n' >"${WORKTREE_ROOT}/graphify-out/cache/semantic-deep"
if run_setup "${WORKTREE_ROOT}" >"${SANDBOX}/semantic-deep-file.out" 2>"${SANDBOX}/semantic-deep-file.err"; then
  echo "setup unexpectedly replaced a semantic-deep cache file" >&2
  exit 1
fi
grep -Fq "graphify-out/cache/semantic-deep already exists" "${SANDBOX}/semantic-deep-file.err"
grep -Fqx do-not-overwrite "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep"
rm "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep"
ln -s "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic-deep" "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep"

unlink "${WORKTREE_ROOT}/docs/literature/pdf"
if run_setup "${WORKTREE_ROOT}" --check >"${SANDBOX}/missing-pdf.out" 2>"${SANDBOX}/missing-pdf.err"; then
  echo "--check unexpectedly accepted a missing PDF cache link" >&2
  exit 1
fi
grep -Fq "docs/literature/pdf is not linked" "${SANDBOX}/missing-pdf.err"
ln -s "${SHARED_ROOT}/docs/literature/pdf" "${WORKTREE_ROOT}/docs/literature/pdf"

unlink "${WORKTREE_ROOT}/.env"
if run_setup "${WORKTREE_ROOT}" --check >"${SANDBOX}/missing-env.out" 2>"${SANDBOX}/missing-env.err"; then
  echo "--check unexpectedly accepted a missing .env" >&2
  exit 1
fi
grep -Fq ".env is missing" "${SANDBOX}/missing-env.err"
ln -s .env.example "${WORKTREE_ROOT}/.env"

mkdir -p "${COLLISION_ROOT}/graphify-out"
printf 'keep\n' >"${COLLISION_ROOT}/graphify-out/graph.json"
if run_setup "${COLLISION_ROOT}" >"${SANDBOX}/collision.out" 2>"${SANDBOX}/collision.err"; then
  echo "setup unexpectedly replaced an unowned Graphify collision" >&2
  exit 1
fi
grep -Fq "destination collision" "${SANDBOX}/collision.err"
grep -Fqx keep "${COLLISION_ROOT}/graphify-out/graph.json"

unlink "${SHARED_ROOT}/aria_nbv/.venv/bin/python"
if run_setup "${WORKTREE_ROOT}" --check >"${SANDBOX}/missing-python.out" 2>"${SANDBOX}/missing-python.err"; then
  echo "--check unexpectedly accepted a missing shared Python" >&2
  exit 1
fi
grep -Fq "shared Python is not executable" "${SANDBOX}/missing-python.err"
ln -s "$(command -v python3)" "${SHARED_ROOT}/aria_nbv/.venv/bin/python"

# Invalid source input is rejected before any writes to an unseeded linked worktree.
rm "${SHARED_ROOT}/graphify-out/manifest.json"
if run_setup "${COLLISION_ROOT}" >"${SANDBOX}/missing.out" 2>"${SANDBOX}/missing.err"; then
  echo "setup unexpectedly accepted a missing parent manifest" >&2
  exit 1
fi
grep -Fq "source manifest must be a regular local file" "${SANDBOX}/missing.err"

echo "Worktree environment setup: PASS"
