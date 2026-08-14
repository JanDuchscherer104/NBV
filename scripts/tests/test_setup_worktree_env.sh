#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/aria-worktree-env.XXXXXX")"
trap 'rm -rf "${SANDBOX}"' EXIT

SHARED_ROOT="${SANDBOX}/shared"
WORKTREE_ROOT="${SANDBOX}/worktree"
SECOND_WORKTREE_ROOT="${SANDBOX}/second-worktree"
FAKE_BIN="${SANDBOX}/bin"

mkdir -p \
  "${SHARED_ROOT}/aria_nbv/.venv/bin" \
  "${SHARED_ROOT}/.data/ase_efm" \
  "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic" \
  "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic-deep" \
  "${SHARED_ROOT}/.data/offline_cache" \
  "${SHARED_ROOT}/docs/literature/pdf" \
  "${WORKTREE_ROOT}/aria_nbv" \
  "${WORKTREE_ROOT}/docs/literature" \
  "${WORKTREE_ROOT}/.codex/environments" \
  "${WORKTREE_ROOT}/scripts" \
  "${SECOND_WORKTREE_ROOT}/aria_nbv" \
  "${SECOND_WORKTREE_ROOT}/docs/literature" \
  "${SECOND_WORKTREE_ROOT}/scripts" \
  "${FAKE_BIN}"
ln -s "$(command -v python3)" "${SHARED_ROOT}/aria_nbv/.venv/bin/python"
cp "${REPO_ROOT}/scripts/setup_worktree_env.sh" "${WORKTREE_ROOT}/scripts/"
cp "${REPO_ROOT}/.env.example" "${WORKTREE_ROOT}/"
cp "${REPO_ROOT}/.codex/environments/aria-nbv.toml" "${WORKTREE_ROOT}/.codex/environments/"
cp "${REPO_ROOT}/scripts/setup_worktree_env.sh" "${SECOND_WORKTREE_ROOT}/scripts/"
cp "${REPO_ROOT}/.env.example" "${SECOND_WORKTREE_ROOT}/"

python3 - "${WORKTREE_ROOT}/.codex/environments/aria-nbv.toml" <<'PY'
import sys
import tomllib

environment = tomllib.load(open(sys.argv[1], "rb"))
assert environment["version"] == 1
assert environment["name"] == "ARIA-NBV shared runtime"
assert environment["setup"]["script"].strip() == (
    'ARIA_NBV_SHARED_ROOT="$CODEX_SOURCE_WORKSPACE_PATH" '
    'bash "$CODEX_WORKTREE_PATH/scripts/setup_worktree_env.sh"'
)
PY

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

git -C "${WORKTREE_ROOT}" init -q
git -C "${SECOND_WORKTREE_ROOT}" init -q
git -C "${WORKTREE_ROOT}" config core.worktree "${SANDBOX}/stale-worktree"
git -C "${SECOND_WORKTREE_ROOT}" config core.worktree "${SANDBOX}/stale-second-worktree"
[[ "$(git -C "${WORKTREE_ROOT}" rev-parse --is-inside-work-tree)" == false ]]
[[ "$(git -C "${SECOND_WORKTREE_ROOT}" rev-parse --is-inside-work-tree)" == false ]]

if ARIA_NBV_SHARED_ROOT="${SHARED_ROOT}" \
  PATH="${FAKE_BIN}:${PATH}" \
  bash "${WORKTREE_ROOT}/scripts/setup_worktree_env.sh" --check \
  >"${SANDBOX}/check.out" 2>"${SANDBOX}/check.err"; then
  echo "--check unexpectedly accepted a fresh worktree" >&2
  exit 1
fi
grep -Fq ".venv is not linked" "${SANDBOX}/check.err"
[[ ! -e "${WORKTREE_ROOT}/.data" ]]

ARIA_NBV_SHARED_ROOT="${SHARED_ROOT}" \
  PATH="${FAKE_BIN}:${PATH}" \
  bash "${WORKTREE_ROOT}/scripts/setup_worktree_env.sh"

[[ -d "${WORKTREE_ROOT}/.data" ]]
[[ -L "${WORKTREE_ROOT}/.data/ase_efm" ]]
[[ -L "${WORKTREE_ROOT}/.data/offline_cache" ]]
[[ -L "${WORKTREE_ROOT}/docs/literature/pdf" ]]
[[ -L "${WORKTREE_ROOT}/.env" ]]
[[ ! -e "${WORKTREE_ROOT}/.data/graphify-semantic-cache" ]]
[[ ! -L "${WORKTREE_ROOT}/.data/graphify-semantic-cache" ]]
[[ -L "${WORKTREE_ROOT}/graphify-out/cache/semantic" ]]
[[ -L "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep" ]]
[[ "$(readlink -f "${WORKTREE_ROOT}/graphify-out/cache/semantic")" == "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic" ]]
[[ "$(readlink -f "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep")" == "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic-deep" ]]

ARIA_NBV_SHARED_ROOT="${SHARED_ROOT}" \
  PATH="${FAKE_BIN}:${PATH}" \
  bash "${SECOND_WORKTREE_ROOT}/scripts/setup_worktree_env.sh"

[[ "$(readlink -f "${SECOND_WORKTREE_ROOT}/graphify-out/cache/semantic")" == "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic" ]]
[[ "$(readlink -f "${SECOND_WORKTREE_ROOT}/graphify-out/cache/semantic-deep")" == "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic-deep" ]]
[[ ! -e "${SECOND_WORKTREE_ROOT}/.data/graphify-semantic-cache" ]]
[[ ! -L "${SECOND_WORKTREE_ROOT}/.data/graphify-semantic-cache" ]]
printf 'cache-hit\n' >"${WORKTREE_ROOT}/graphify-out/cache/semantic/cache-hit.json"
grep -Fqx 'cache-hit' "${SECOND_WORKTREE_ROOT}/graphify-out/cache/semantic/cache-hit.json"
touch "${WORKTREE_ROOT}/graphify-out/graph.json"
[[ ! -e "${SECOND_WORKTREE_ROOT}/graphify-out/graph.json" ]]
[[ ! -L "${WORKTREE_ROOT}/graphify-out" ]]
[[ ! -L "${SECOND_WORKTREE_ROOT}/graphify-out" ]]

(
  cd "${WORKTREE_ROOT}"
  PATH="${FAKE_BIN}:${PATH}"
  # shellcheck disable=SC1091
  source .env
  [[ "$(command -v python)" == "${WORKTREE_ROOT}/aria_nbv/.venv/bin/python" ]]
  python -c 'import sys; raise SystemExit(0 if sys.executable else 1)'
  [[ -z "${ARIA_NBV_MAMBA_ENV:-}" ]]
  ! declare -F aria_nbv_run >/dev/null
)

ARIA_NBV_SHARED_ROOT="${SHARED_ROOT}" \
  PATH="${FAKE_BIN}:${PATH}" \
  bash "${WORKTREE_ROOT}/scripts/setup_worktree_env.sh" --check

unlink "${WORKTREE_ROOT}/graphify-out/cache/semantic"
ln -s "${SHARED_ROOT}/.data/offline_cache" \
  "${WORKTREE_ROOT}/graphify-out/cache/semantic"
if ARIA_NBV_SHARED_ROOT="${SHARED_ROOT}" \
  PATH="${FAKE_BIN}:${PATH}" \
  bash "${WORKTREE_ROOT}/scripts/setup_worktree_env.sh" \
  >"${SANDBOX}/wrong-semantic.out" 2>"${SANDBOX}/wrong-semantic.err"; then
  echo "setup unexpectedly replaced a wrong semantic cache link" >&2
  exit 1
fi
grep -Fq "graphify-out/cache/semantic points somewhere else" "${SANDBOX}/wrong-semantic.err"
[[ "$(readlink -f "${WORKTREE_ROOT}/graphify-out/cache/semantic")" == "${SHARED_ROOT}/.data/offline_cache" ]]
unlink "${WORKTREE_ROOT}/graphify-out/cache/semantic"
ln -s "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic" \
  "${WORKTREE_ROOT}/graphify-out/cache/semantic"

unlink "${WORKTREE_ROOT}/graphify-out/cache/semantic"
if ARIA_NBV_SHARED_ROOT="${SHARED_ROOT}" \
  PATH="${FAKE_BIN}:${PATH}" \
  bash "${WORKTREE_ROOT}/scripts/setup_worktree_env.sh" --check \
  >"${SANDBOX}/missing-semantic.out" 2>"${SANDBOX}/missing-semantic.err"; then
  echo "--check unexpectedly accepted a missing semantic cache link" >&2
  exit 1
fi
grep -Fq "graphify-out/cache/semantic is not linked" "${SANDBOX}/missing-semantic.err"
[[ ! -e "${WORKTREE_ROOT}/graphify-out/cache/semantic" ]]
ln -s "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic" "${WORKTREE_ROOT}/graphify-out/cache/semantic"

unlink "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep"
mkdir "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep"
touch "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep/keep"
if ARIA_NBV_SHARED_ROOT="${SHARED_ROOT}" \
  PATH="${FAKE_BIN}:${PATH}" \
  bash "${WORKTREE_ROOT}/scripts/setup_worktree_env.sh" \
  >"${SANDBOX}/semantic-collision.out" 2>"${SANDBOX}/semantic-collision.err"; then
  echo "setup unexpectedly replaced a semantic cache collision" >&2
  exit 1
fi
grep -Fq "graphify-out/cache/semantic-deep already exists" "${SANDBOX}/semantic-collision.err"
[[ -f "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep/keep" ]]
rm -f "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep/keep"
rmdir "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep"
ln -s "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic-deep" \
  "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep"

unlink "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep"
printf 'do-not-overwrite\n' >"${WORKTREE_ROOT}/graphify-out/cache/semantic-deep"
if ARIA_NBV_SHARED_ROOT="${SHARED_ROOT}" \
  PATH="${FAKE_BIN}:${PATH}" \
  bash "${WORKTREE_ROOT}/scripts/setup_worktree_env.sh" \
  >"${SANDBOX}/semantic-deep-file.out" 2>"${SANDBOX}/semantic-deep-file.err"; then
  echo "setup unexpectedly replaced a semantic-deep cache file" >&2
  exit 1
fi
grep -Fq "graphify-out/cache/semantic-deep already exists" "${SANDBOX}/semantic-deep-file.err"
grep -Fqx 'do-not-overwrite' "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep"
rm -f "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep"
ln -s "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic-deep" \
  "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep"

unlink "${WORKTREE_ROOT}/docs/literature/pdf"
if ARIA_NBV_SHARED_ROOT="${SHARED_ROOT}" \
  PATH="${FAKE_BIN}:${PATH}" \
  bash "${WORKTREE_ROOT}/scripts/setup_worktree_env.sh" --check \
  >"${SANDBOX}/missing-pdf.out" 2>"${SANDBOX}/missing-pdf.err"; then
  echo "--check unexpectedly accepted a missing PDF cache link" >&2
  exit 1
fi
grep -Fq "docs/literature/pdf is not linked" "${SANDBOX}/missing-pdf.err"

ln -s "${SHARED_ROOT}/docs/literature/pdf" "${WORKTREE_ROOT}/docs/literature/pdf"

unlink "${WORKTREE_ROOT}/.env"
if ARIA_NBV_SHARED_ROOT="${SHARED_ROOT}" \
  PATH="${FAKE_BIN}:${PATH}" \
  bash "${WORKTREE_ROOT}/scripts/setup_worktree_env.sh" --check \
  >"${SANDBOX}/missing-env.out" 2>"${SANDBOX}/missing-env.err"; then
  echo "--check unexpectedly accepted a missing .env" >&2
  exit 1
fi
grep -Fq ".env is missing" "${SANDBOX}/missing-env.err"

ln -s .env.example "${WORKTREE_ROOT}/.env"
unlink "${SHARED_ROOT}/aria_nbv/.venv/bin/python"
if ARIA_NBV_SHARED_ROOT="${SHARED_ROOT}" \
  PATH="${FAKE_BIN}:${PATH}" \
  bash "${WORKTREE_ROOT}/scripts/setup_worktree_env.sh" --check \
  >"${SANDBOX}/missing-python.out" 2>"${SANDBOX}/missing-python.err"; then
  echo "--check unexpectedly accepted a missing shared Python" >&2
  exit 1
fi
grep -Fq "shared Python is not executable" "${SANDBOX}/missing-python.err"

echo "Worktree environment setup: PASS"
