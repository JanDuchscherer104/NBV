#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
SANDBOX="$(mktemp -d "${TMPDIR:-/tmp}/aria-worktree-env.XXXXXX")"
trap 'rm -rf "${SANDBOX}"' EXIT

SHARED_ROOT="${SANDBOX}/shared"
WORKTREE_ROOT="${SANDBOX}/worktree"
FAKE_BIN="${SANDBOX}/bin"

mkdir -p \
  "${SHARED_ROOT}/aria_nbv/.venv/bin" \
  "${SHARED_ROOT}/.data/ase_efm" \
  "${WORKTREE_ROOT}/aria_nbv" \
  "${WORKTREE_ROOT}/scripts" \
  "${FAKE_BIN}"
ln -s "$(command -v python3)" "${SHARED_ROOT}/aria_nbv/.venv/bin/python"
cp "${REPO_ROOT}/scripts/setup_worktree_env.sh" "${WORKTREE_ROOT}/scripts/"

cat >"${FAKE_BIN}/readlink" <<'EOF'
#!/usr/bin/env bash
echo "readlink must not be used" >&2
exit 99
EOF
chmod +x "${FAKE_BIN}/readlink"

git -C "${WORKTREE_ROOT}" init -q

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

ARIA_NBV_SHARED_ROOT="${SHARED_ROOT}" \
  PATH="${FAKE_BIN}:${PATH}" \
  bash "${WORKTREE_ROOT}/scripts/setup_worktree_env.sh" --check

echo "Worktree environment setup: PASS"
