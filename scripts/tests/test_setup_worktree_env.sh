#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SANDBOX="$(cd "$(mktemp -d "${TMPDIR:-/tmp}/aria-worktree-env.XXXXXX")" && pwd -P)"
trap 'rm -rf "${SANDBOX}"' EXIT

SHARED_ROOT="${SANDBOX}/shared"
WORKTREE_ROOT="${SANDBOX}/worktree"
SECOND_WORKTREE_ROOT="${SANDBOX}/second-worktree"
EXPLICIT_CHILD_ROOT="${SANDBOX}/explicit-child"
STALE_CHILD_ROOT="${SANDBOX}/stale-child"
AMBIGUOUS_CHILD_ROOT="${SANDBOX}/ambiguous-child"
TRACKED_PDF_ROOT="${SANDBOX}/tracked-pdf-worktree"
COLLISION_ROOT="${SANDBOX}/collision-worktree"
UNSAFE_OUT_ROOT="${SANDBOX}/unsafe-out-worktree"
UNSAFE_CACHE_ROOT="${SANDBOX}/unsafe-cache-worktree"
NON_GIT_WORKTREE_ROOT="${SANDBOX}/non-git-worktree"
NON_GIT_SHARED_ROOT="${SANDBOX}/non-git-shared"
FOREIGN_WORKTREE_ROOT="${SANDBOX}/foreign-worktree"
FOREIGN_SHARED_ROOT="${SANDBOX}/foreign-shared"
FAKE_BIN="${SANDBOX}/bin"
HOST_PYTHON="$(command -v python3)"

GRAPHIFY_CLI="$(command -v graphify)"
[[ -n "${GRAPHIFY_CLI}" && -f "${GRAPHIFY_CLI}" ]] || {
  echo "graphify CLI is required for the seeder trust fixture" >&2
  exit 1
}
GRAPHIFY_INTERPRETER="$(sed -n '1s/^#!//p' "${GRAPHIFY_CLI}")"
[[ -n "${GRAPHIFY_INTERPRETER}" && "${GRAPHIFY_INTERPRETER}" == /* ]] || {
  echo "graphify CLI must have an absolute interpreter shebang" >&2
  exit 1
}

mkdir -p \
  "${SHARED_ROOT}/aria_nbv/.venv/bin" \
  "${SHARED_ROOT}/.data/ase_efm" \
  "${SHARED_ROOT}/.data/offline_cache" \
  "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic" \
  "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic-deep" \
  "${SHARED_ROOT}/docs/literature/pdf" \
  "${SHARED_ROOT}/scripts" "${SHARED_ROOT}/.codex/environments" "${FAKE_BIN}"
cp "${REPO_ROOT}/scripts/setup_worktree_env.sh" "${SHARED_ROOT}/scripts/"
cp "${REPO_ROOT}/scripts/setup_codex_worktree_env.sh" "${SHARED_ROOT}/scripts/"
cp "${REPO_ROOT}/scripts/graphify_worktree_seed.py" "${SHARED_ROOT}/scripts/"
cp "${REPO_ROOT}/.codex/environments/aria-nbv.toml" \
  "${SHARED_ROOT}/.codex/environments/"
cat >"${SHARED_ROOT}/scripts/reconcile_graphify_worktree.py" <<EOF
#!/usr/bin/env python3
from pathlib import Path
import sys
Path("${SANDBOX}/reconcile.log").open("a", encoding="utf-8").write(" ".join(sys.argv[1:]) + "\\n")
EOF
cat >"${SHARED_ROOT}/scripts/check_graphify_freshness.py" <<EOF
#!/usr/bin/env python3
import os
from pathlib import Path
import sys
Path("${SANDBOX}/freshness.log").open("a", encoding="utf-8").write(" ".join(sys.argv[1:]) + "\\n")
root = Path.cwd()
admitted = root == Path("${WORKTREE_ROOT}")
admitted = admitted or (
    root == Path("${SHARED_ROOT}")
    and os.environ.get("ARIA_TEST_PRIMARY_UNUSABLE") != "1"
)
admitted = admitted or (
    root == Path("${SECOND_WORKTREE_ROOT}")
    and os.environ.get("ARIA_TEST_ADMIT_SECOND") == "1"
)
admitted = admitted or (
    root == Path("${EXPLICIT_CHILD_ROOT}")
    and os.environ.get("ARIA_TEST_ADMIT_EXPLICIT") == "1"
)
raise SystemExit(0 if admitted else 1)
EOF
chmod +x "${SHARED_ROOT}/scripts/reconcile_graphify_worktree.py" \
  "${SHARED_ROOT}/scripts/check_graphify_freshness.py"
cp "${REPO_ROOT}/.env.example" "${SHARED_ROOT}/"
touch "${SHARED_ROOT}/aria_nbv/.gitkeep" "${SHARED_ROOT}/docs/literature/.gitkeep"

git -C "${SHARED_ROOT}" init -q
git -C "${SHARED_ROOT}" config user.email test@example.invalid
git -C "${SHARED_ROOT}" config user.name test
git -C "${SHARED_ROOT}" config extensions.worktreeConfig true
git -C "${SHARED_ROOT}" add .
git -C "${SHARED_ROOT}" commit -qm fixture
ln -s "$(command -v python3)" "${SHARED_ROOT}/aria_nbv/.venv/bin/python"
git -C "${SHARED_ROOT}" worktree add -qb seed-child "${WORKTREE_ROOT}"
git -C "${SHARED_ROOT}" worktree add -qb seed-second "${SECOND_WORKTREE_ROOT}"
git -C "${SHARED_ROOT}" worktree add -qb seed-explicit-child "${EXPLICIT_CHILD_ROOT}"
git -C "${SHARED_ROOT}" worktree add -qb seed-stale-child "${STALE_CHILD_ROOT}"
git -C "${SHARED_ROOT}" worktree add -qb seed-ambiguous-child "${AMBIGUOUS_CHILD_ROOT}"
git -C "${SHARED_ROOT}" worktree add -qb seed-tracked-pdf "${TRACKED_PDF_ROOT}"
git -C "${SHARED_ROOT}" worktree add -qb seed-collision "${COLLISION_ROOT}"
git -C "${SHARED_ROOT}" worktree add -qb seed-unsafe-out "${UNSAFE_OUT_ROOT}"
git -C "${SHARED_ROOT}" worktree add -qb seed-unsafe-cache "${UNSAFE_CACHE_ROOT}"
git -C "${SHARED_ROOT}" worktree add -qb seed-non-git "${NON_GIT_WORKTREE_ROOT}"
git -C "${SHARED_ROOT}" worktree add -qb seed-foreign "${FOREIGN_WORKTREE_ROOT}"

mkdir -p \
  "${NON_GIT_SHARED_ROOT}/aria_nbv/.venv/bin" \
  "${NON_GIT_SHARED_ROOT}/.data/graphify-semantic-cache/semantic" \
  "${NON_GIT_SHARED_ROOT}/.data/graphify-semantic-cache/semantic-deep"
ln -s "$(command -v python3)" "${NON_GIT_SHARED_ROOT}/aria_nbv/.venv/bin/python"

mkdir -p "${FOREIGN_SHARED_ROOT}/aria_nbv/.venv/bin" "${FOREIGN_SHARED_ROOT}/.data"
git -C "${FOREIGN_SHARED_ROOT}" init -q
cat >"${FOREIGN_SHARED_ROOT}/aria_nbv/.venv/bin/python" <<EOF
#!/usr/bin/env bash
touch "${SANDBOX}/foreign-parent-python-executed"
EOF
chmod +x "${FOREIGN_SHARED_ROOT}/aria_nbv/.venv/bin/python"

# The source seed is deliberately untracked. Graphify output is an ignored,
# derived artifact and setup must nevertheless require a complete valid parent.
mkdir -p "${SHARED_ROOT}/graphify-out" "${SHARED_ROOT}/graphify-input"
cat >"${SHARED_ROOT}/graphify-out/graph.json" <<EOF
{"built_at_commit":"$(git -C "${SHARED_ROOT}" rev-parse HEAD)","nodes":[{"source_file":"graphify-input/index.md"}]}
EOF
cat >"${SHARED_ROOT}/graphify-out/manifest.json" <<'EOF'
{"graphify-input/index.md":{"semantic_hash":"fixture"}}
EOF
printf '%s\n' "${GRAPHIFY_INTERPRETER}" >"${SHARED_ROOT}/graphify-out/.graphify_python"
[[ "$(cat "${SHARED_ROOT}/graphify-out/.graphify_python")" == "${GRAPHIFY_INTERPRETER}" ]]
cat >"${SHARED_ROOT}/graphify-input/index.md" <<'EOF'
---
title: fixture
---
# fixture
EOF
# These are explicitly never inherited.
mkdir -p "${SHARED_ROOT}/graphify-out/cache"
ln -s "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic" \
  "${SHARED_ROOT}/graphify-out/cache/semantic"
ln -s "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic-deep" \
  "${SHARED_ROOT}/graphify-out/cache/semantic-deep"
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

cat >"${FAKE_BIN}/python3" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >>"${SANDBOX}/source-admission.log"
if [[ "\$*" == *"check_graphify_freshness.py"* ]]; then
  exec "${HOST_PYTHON}" "\$@"
fi
exit 0
EOF
chmod +x "${FAKE_BIN}/python3"

# Preserve d6a's explicit-Git-dir regression: ambient Git discovery reports a
# stale worktree, while setup must still address this child explicitly.
git -C "${WORKTREE_ROOT}" config --worktree core.worktree "${SANDBOX}/stale-worktree"
git -C "${SECOND_WORKTREE_ROOT}" config --worktree core.worktree "${SANDBOX}/stale-second-worktree"
[[ "$(git -C "${WORKTREE_ROOT}" rev-parse --is-inside-work-tree)" == false ]]
[[ "$(git -C "${SECOND_WORKTREE_ROOT}" rev-parse --is-inside-work-tree)" == false ]]

run_setup() {
  ARIA_NBV_SHARED_ROOT="${SHARED_ROOT}" ARIA_NBV_CANONICAL_PRIMARY="${SHARED_ROOT}" PATH="${FAKE_BIN}:${PATH}" \
    bash "$1/scripts/setup_worktree_env.sh" "${@:2}"
}

CODEX_SETUP_SCRIPT="$(python3 - "${SHARED_ROOT}/.codex/environments/aria-nbv.toml" <<'PY'
import sys
import tomllib

environment = tomllib.load(open(sys.argv[1], "rb"))
assert environment["version"] == 1
assert environment["name"] == "ARIA-NBV shared runtime"
script = environment["setup"]["script"].strip()
assert script == 'bash "$CODEX_WORKTREE_PATH/scripts/setup_codex_worktree_env.sh"'
print(script)
PY
)"

run_codex_setup() {
  CODEX_WORKTREE_PATH="$1" CODEX_SOURCE_WORKSPACE_PATH="$2" \
    ARIA_TEST_PRIMARY_UNUSABLE="${ARIA_TEST_PRIMARY_UNUSABLE:-}" \
    ARIA_TEST_ADMIT_SECOND="${ARIA_TEST_ADMIT_SECOND:-}" \
    ARIA_TEST_ADMIT_EXPLICIT="${ARIA_TEST_ADMIT_EXPLICIT:-}" \
    PATH="${FAKE_BIN}:${PATH}" bash -c "${CODEX_SETUP_SCRIPT}"
}

# Parent selection is explicit; setup must never silently choose Git's first
# registered worktree when the Codex-provided parent is absent.
if ARIA_NBV_SHARED_ROOT= PATH="${FAKE_BIN}:${PATH}" \
  bash "${WORKTREE_ROOT}/scripts/setup_worktree_env.sh" --check \
  >"${SANDBOX}/missing-parent.out" 2>"${SANDBOX}/missing-parent.err"; then
  echo "setup unexpectedly accepted a missing explicit parent" >&2
  exit 1
fi
grep -Fq "ARIA_NBV_SHARED_ROOT must identify the parent worktree" \
  "${SANDBOX}/missing-parent.err"

snapshot_tree() {
  local root="$1"
  python3 - "${root}" <<'PY'
import hashlib
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
entries: list[str] = []
digests: list[str] = []
for path in root.rglob("*"):
    relative = path.relative_to(root).as_posix()
    if path.is_symlink():
        kind = "l"
    elif path.is_dir():
        kind = "d"
    elif path.is_file():
        kind = "f"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        digests.append(f"{digest}  {path}")
    else:
        kind = "?"
    entries.append(f"{relative} {kind}")
print("\n".join(sorted(entries)))
if entries and digests:
    print()
print("\n".join(sorted(digests)))
PY
}

# The public Codex boundary rejects malformed mode declarations before it ranks
# a parent or can mutate the destination, and reports one actionable line.
mode_before="$(snapshot_tree "${STALE_CHILD_ROOT}")"
if CODEX_WORKTREE_PATH="${STALE_CHILD_ROOT}" \
  CODEX_SOURCE_WORKSPACE_PATH="${SHARED_ROOT}" \
  ARIA_NBV_GRAPHIFY_MODES="deep,standard" \
  PATH="${FAKE_BIN}:${PATH}" bash -c "${CODEX_SETUP_SCRIPT}" \
  >"${SANDBOX}/bad-mode.out" 2>"${SANDBOX}/bad-mode.err"; then
  echo "Codex setup unexpectedly accepted a reordered Graphify mode list" >&2
  exit 1
fi
[[ ! -s "${SANDBOX}/bad-mode.out" ]]
[[ "$(wc -l <"${SANDBOX}/bad-mode.err")" -eq 1 ]]
grep -Fqx "error: ARIA_NBV_GRAPHIFY_MODES must be standard, deep, or standard,deep" \
  "${SANDBOX}/bad-mode.err"
[[ "$(snapshot_tree "${STALE_CHILD_ROOT}")" == "${mode_before}" ]]

# A foreign explicit parent must fail solely from Git topology. Its executable
# must not run and an unseeded child must remain byte-for-byte untouched.
foreign_before="$(snapshot_tree "${FOREIGN_WORKTREE_ROOT}")"
if ARIA_NBV_SHARED_ROOT="${FOREIGN_SHARED_ROOT}" PATH="${FAKE_BIN}:${PATH}" \
  bash "${FOREIGN_WORKTREE_ROOT}/scripts/setup_worktree_env.sh" --check \
  >"${SANDBOX}/foreign.out" 2>"${SANDBOX}/foreign.err"; then
  echo "setup unexpectedly accepted a foreign shared root" >&2
  exit 1
fi
grep -Fq "same Git common directory" "${SANDBOX}/foreign.err"
[[ ! -e "${SANDBOX}/foreign-parent-python-executed" ]]
[[ "$(snapshot_tree "${FOREIGN_WORKTREE_ROOT}")" == "${foreign_before}" ]]

# A registered explicit parent that is Graphify-unusable is rejected by the
# repository-owned checker before its runtime executes or the child changes.
mkdir -p "${SECOND_WORKTREE_ROOT}/aria_nbv/.venv/bin"
cat >"${SECOND_WORKTREE_ROOT}/aria_nbv/.venv/bin/python" <<EOF
#!/usr/bin/env bash
touch "${SANDBOX}/stale-parent-python-executed"
EOF
chmod +x "${SECOND_WORKTREE_ROOT}/aria_nbv/.venv/bin/python"
stale_before="$(snapshot_tree "${STALE_CHILD_ROOT}")"
if ARIA_NBV_SHARED_ROOT="${SECOND_WORKTREE_ROOT}" ARIA_NBV_CANONICAL_PRIMARY="${SHARED_ROOT}" PATH="${PATH}" \
  bash "${STALE_CHILD_ROOT}/scripts/setup_worktree_env.sh" --check \
  >"${SANDBOX}/stale-parent.out" 2>"${SANDBOX}/stale-parent.err"; then
  echo "setup unexpectedly accepted a Graphify-unusable explicit parent" >&2
  exit 1
fi
grep -Fq "shared parent Graphify generation is not query-admissible" \
  "${SANDBOX}/stale-parent.err"
[[ ! -e "${SANDBOX}/stale-parent-python-executed" ]]
[[ "$(snapshot_tree "${STALE_CHILD_ROOT}")" == "${stale_before}" ]]
rm "${SECOND_WORKTREE_ROOT}/aria_nbv/.venv/bin/python"
rmdir "${SECOND_WORKTREE_ROOT}/aria_nbv/.venv/bin" "${SECOND_WORKTREE_ROOT}/aria_nbv/.venv"

# A shared root without Git ownership cannot supply a mandatory Graphify seed.
# Both modes must reject it before creating or linking anything in the child.
non_git_before="$(snapshot_tree "${NON_GIT_WORKTREE_ROOT}")"
for mode in normal check; do
  args=()
  [[ "${mode}" == check ]] && args+=(--check)
  if ARIA_NBV_SHARED_ROOT="${NON_GIT_SHARED_ROOT}" PATH="${FAKE_BIN}:${PATH}" \
    bash "${NON_GIT_WORKTREE_ROOT}/scripts/setup_worktree_env.sh" "${args[@]}" \
    >"${SANDBOX}/non-git-${mode}.out" 2>"${SANDBOX}/non-git-${mode}.err"; then
    echo "setup unexpectedly accepted a non-Git shared root in ${mode} mode" >&2
    exit 1
  fi
  grep -Fq "shared root is not a Git worktree" "${SANDBOX}/non-git-${mode}.err"
  [[ "$(snapshot_tree "${NON_GIT_WORKTREE_ROOT}")" == "${non_git_before}" ]]
done

# Setup must reject Graphify directory symlinks before mkdir or cache linking can
# mutate an existing external target or create a dangling target.
for relative in graphify-out graphify-out/cache; do
  case "${relative}" in
    graphify-out) unsafe_root="${UNSAFE_OUT_ROOT}" ;;
    *) unsafe_root="${UNSAFE_CACHE_ROOT}"; mkdir -p "${unsafe_root}/graphify-out" ;;
  esac
  for target_state in existing dangling; do
    external="${SANDBOX}/${relative//\//-}-${target_state}"
    if [[ "${target_state}" == existing ]]; then
      mkdir "${external}"
      printf 'preserve\0bytes' >"${external}/keep.bin"
      before="$(snapshot_tree "${external}")"
    fi
    ln -s "${external}" "${unsafe_root}/${relative}"
    if run_setup "${unsafe_root}" >"${SANDBOX}/unsafe.out" 2>"${SANDBOX}/unsafe.err"; then
      echo "setup unexpectedly accepted ${relative} ${target_state} symlink" >&2
      exit 1
    fi
    grep -Fq "unsafe destination parent" "${SANDBOX}/unsafe.err"
    if [[ "${target_state}" == existing ]]; then
      [[ "$(snapshot_tree "${external}")" == "${before}" ]]
    else
      [[ ! -e "${external}" ]]
    fi
    unlink "${unsafe_root}/${relative}"
  done
done

if run_setup "${WORKTREE_ROOT}" --check >"${SANDBOX}/fresh.out" 2>"${SANDBOX}/fresh.err"; then
  echo "--check unexpectedly accepted an unseeded worktree" >&2
  exit 1
fi
grep -Fq ".venv is not linked" "${SANDBOX}/fresh.err"
[[ ! -e "${WORKTREE_ROOT}/graphify-out/graph.json" ]]

# A mutating setup creates only missing regular leaves under the authenticated
# primary cache root; read-only setup keeps the stricter absence failure above.
rmdir "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic" \
  "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic-deep" \
  "${SHARED_ROOT}/.data/graphify-semantic-cache"
run_setup "${WORKTREE_ROOT}"
[[ -d "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic" ]]
[[ -d "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic-deep" ]]
grep -Fqx -- "--usable --quiet" "${SANDBOX}/freshness.log"
[[ ! -e "${SANDBOX}/reconcile.log" ]]
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

# A newly tracked paper makes the PDF directory an exact local input. Setup
# must preserve it instead of trying to replace its parent directory with the
# legacy shared-cache symlink.
mkdir -p "${TRACKED_PDF_ROOT}/docs/literature/pdf"
printf 'tracked paper\n' >"${TRACKED_PDF_ROOT}/docs/literature/pdf/tracked.pdf"
git -C "${TRACKED_PDF_ROOT}" add -f docs/literature/pdf/tracked.pdf
git -C "${TRACKED_PDF_ROOT}" commit -qm "track paper fixture"
run_setup "${TRACKED_PDF_ROOT}" \
  >"${SANDBOX}/tracked-pdf.out" 2>"${SANDBOX}/tracked-pdf.err"
[[ -f "${TRACKED_PDF_ROOT}/docs/literature/pdf/tracked.pdf" ]]
[[ ! -L "${TRACKED_PDF_ROOT}/docs/literature/pdf" ]]
[[ -L "${WORKTREE_ROOT}/graphify-out/cache/semantic" ]]
[[ -L "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep" ]]

# The canonical primary has no parent seed requirement: its maintenance route
# validates its own cache root and reconciles the existing local graph quietly.
CODEX_WORKTREE_PATH="${SHARED_ROOT}" \
  bash "${SHARED_ROOT}/scripts/setup_codex_worktree_env.sh" --maintain --quiet \
  >"${SANDBOX}/maintain-primary.out" 2>"${SANDBOX}/maintain-primary.err"
[[ ! -s "${SANDBOX}/maintain-primary.out" && ! -s "${SANDBOX}/maintain-primary.err" ]]

# Execute the exact Codex environment bridge with the source variable empty.
# When the canonical primary is unusable, it must choose the nearest admitted
# ancestor sibling rather than worktree-list order. Advance the destination by
# one empty commit so the seeded worktree is its only admitted ancestor.
git --git-dir="$(git -C "${SECOND_WORKTREE_ROOT}" rev-parse --absolute-git-dir)" \
  --work-tree="${SECOND_WORKTREE_ROOT}" commit --allow-empty -qm "destination ahead"
ARIA_TEST_PRIMARY_UNUSABLE=1 run_codex_setup "${SECOND_WORKTREE_ROOT}" "" \
  >"${SANDBOX}/second-codex.out" 2>"${SANDBOX}/second-codex.err"
[[ ! -s "${SANDBOX}/second-codex.out" && ! -s "${SANDBOX}/second-codex.err" ]]
python3 - "${SECOND_WORKTREE_ROOT}/graphify-out/.aria-worktree-seed.json" "${WORKTREE_ROOT}" <<'PY'
import json
import sys
from pathlib import Path

sentinel = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert sentinel["source_worktree"] == str(Path(sys.argv[2]).resolve())
PY
[[ "$(readlink -f "${SECOND_WORKTREE_ROOT}/graphify-out/cache/semantic")" == "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic" ]]
[[ "$(readlink -f "${SECOND_WORKTREE_ROOT}/graphify-out/cache/semantic-deep")" == "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic-deep" ]]
[[ ! -e "${SECOND_WORKTREE_ROOT}/.data/graphify-semantic-cache" ]]
[[ ! -L "${SECOND_WORKTREE_ROOT}/.data/graphify-semantic-cache" ]]

# A real Codex fork parent remains authoritative even though the canonical
# primary checkout and an admitted sibling are also available. Set this child
# up before the tie-break fixture so each admitted candidate is a valid shared
# runtime as well as a query-admissible Graphify source.
ARIA_TEST_ADMIT_SECOND=1 run_codex_setup "${EXPLICIT_CHILD_ROOT}" "${SECOND_WORKTREE_ROOT}" \
  >"${SANDBOX}/explicit-codex.out" 2>"${SANDBOX}/explicit-codex.err"
[[ ! -s "${SANDBOX}/explicit-codex.out" && ! -s "${SANDBOX}/explicit-codex.err" ]]

# Equally ranked admitted ancestor siblings use a deterministic path tie-break.
git --git-dir="$(git -C "${AMBIGUOUS_CHILD_ROOT}" rev-parse --absolute-git-dir)" \
  --work-tree="${AMBIGUOUS_CHILD_ROOT}" merge --ff-only \
  "$(git --git-dir="$(git -C "${SECOND_WORKTREE_ROOT}" rev-parse --absolute-git-dir)" \
    --work-tree="${SECOND_WORKTREE_ROOT}" rev-parse HEAD)"
ARIA_TEST_PRIMARY_UNUSABLE=1 ARIA_TEST_ADMIT_EXPLICIT=1 \
  run_codex_setup "${AMBIGUOUS_CHILD_ROOT}" "" \
  >"${SANDBOX}/ambiguous.out" 2>"${SANDBOX}/ambiguous.err"
[[ ! -s "${SANDBOX}/ambiguous.out" && ! -s "${SANDBOX}/ambiguous.err" ]]
python3 - "${AMBIGUOUS_CHILD_ROOT}/graphify-out/.aria-worktree-seed.json" \
  "${EXPLICIT_CHILD_ROOT}" <<'PY'
import json
import sys
from pathlib import Path

sentinel = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert sentinel["source_worktree"] == str(Path(sys.argv[2]).resolve())
PY

# Git hooks export destination bindings. The top-level bridge must discard
# those bindings before it validates independent sibling and primary paths.
GIT_DIR="$(git -C "${EXPLICIT_CHILD_ROOT}" rev-parse --absolute-git-dir)" \
GIT_WORK_TREE="${EXPLICIT_CHILD_ROOT}" ARIA_TEST_ADMIT_SECOND=1 \
  run_codex_setup "${EXPLICIT_CHILD_ROOT}" "${SECOND_WORKTREE_ROOT}" \
  >"${SANDBOX}/hook-bound-codex.out" 2>"${SANDBOX}/hook-bound-codex.err"
[[ ! -s "${SANDBOX}/hook-bound-codex.out" && ! -s "${SANDBOX}/hook-bound-codex.err" ]]
python3 - "${EXPLICIT_CHILD_ROOT}/graphify-out/.aria-worktree-seed.json" "${SECOND_WORKTREE_ROOT}" <<'PY'
import json
import sys
from pathlib import Path

sentinel = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert sentinel["source_worktree"] == str(Path(sys.argv[2]).resolve())
PY

# Linked-worktree maintenance first validates the owned local seed and cache
# links; unlike primary maintenance, it cannot reconcile an arbitrary graph.
CODEX_WORKTREE_PATH="${EXPLICIT_CHILD_ROOT}" \
  bash "${EXPLICIT_CHILD_ROOT}/scripts/setup_codex_worktree_env.sh" --maintain --quiet \
  >"${SANDBOX}/maintain-linked.out" 2>"${SANDBOX}/maintain-linked.err"
[[ ! -s "${SANDBOX}/maintain-linked.out" && ! -s "${SANDBOX}/maintain-linked.err" ]]
unlink "${EXPLICIT_CHILD_ROOT}/graphify-out/cache/semantic"
ln -s "${SHARED_ROOT}/.data/offline_cache" "${EXPLICIT_CHILD_ROOT}/graphify-out/cache/semantic"
if CODEX_WORKTREE_PATH="${EXPLICIT_CHILD_ROOT}" \
  bash "${EXPLICIT_CHILD_ROOT}/scripts/setup_codex_worktree_env.sh" --maintain --quiet \
  >"${SANDBOX}/maintain-invalid.out" 2>"${SANDBOX}/maintain-invalid.err"; then
  echo "linked maintenance unexpectedly accepted a tampered cache link" >&2
  exit 1
fi
[[ ! -s "${SANDBOX}/maintain-invalid.out" ]]
[[ "$(wc -l <"${SANDBOX}/maintain-invalid.err")" -eq 1 ]]
grep -Fqx "error: linked worktree Graphify seed is invalid; rerun Codex worktree setup" \
  "${SANDBOX}/maintain-invalid.err"
unlink "${EXPLICIT_CHILD_ROOT}/graphify-out/cache/semantic"
ln -s "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic" \
  "${EXPLICIT_CHILD_ROOT}/graphify-out/cache/semantic"
printf 'cache-hit\n' >"${WORKTREE_ROOT}/graphify-out/cache/semantic/cache-hit.json"
grep -Fqx cache-hit "${SECOND_WORKTREE_ROOT}/graphify-out/cache/semantic/cache-hit.json"
printf '{"built_at_commit":"%s","nodes":[{"source_file":"graphify-input/index.md"}],"fixture":"child"}\n' \
  "$(git -C "${WORKTREE_ROOT}" rev-parse HEAD)" >"${WORKTREE_ROOT}/graphify-out/graph.json"
grep -Fq 'graphify-input/index.md' "${SHARED_ROOT}/graphify-out/graph.json"
[[ ! -e "${SECOND_WORKTREE_ROOT}/graphify-out/graph.json" || "$(cat "${SECOND_WORKTREE_ROOT}/graphify-out/graph.json")" != "$(cat "${WORKTREE_ROOT}/graphify-out/graph.json")" ]]

# Idempotence never overwrites local mutable graph state; --check is read-only.
before="$(sha256sum "${WORKTREE_ROOT}/graphify-out/graph.json")"
run_setup "${WORKTREE_ROOT}"
[[ "$(sha256sum "${WORKTREE_ROOT}/graphify-out/graph.json")" == "${before}" ]]
run_setup "${WORKTREE_ROOT}" --check
[[ "$(sha256sum "${WORKTREE_ROOT}/graphify-out/graph.json")" == "${before}" ]]
grep -Fqx -- "--usable --quiet" "${SANDBOX}/freshness.log"

# The same directory guards apply to normal idempotent and --check paths after
# a child is fully seeded.
for relative in graphify-out graphify-out/cache; do
  held="${WORKTREE_ROOT}/${relative}.held"
  mv "${WORKTREE_ROOT}/${relative}" "${held}"
  for mode in normal check; do
    for target_state in existing dangling; do
      external="${SANDBOX}/owned-${relative//\//-}-${mode}-${target_state}"
      if [[ "${target_state}" == existing ]]; then
        mkdir "${external}"
        printf 'owned-preserve\0bytes' >"${external}/keep.bin"
        before="$(snapshot_tree "${external}")"
      fi
      ln -s "${external}" "${WORKTREE_ROOT}/${relative}"
      args=()
      [[ "${mode}" == check ]] && args+=(--check)
      if run_setup "${WORKTREE_ROOT}" "${args[@]}" >"${SANDBOX}/owned-unsafe.out" 2>"${SANDBOX}/owned-unsafe.err"; then
        echo "setup unexpectedly accepted owned ${relative} ${target_state} symlink in ${mode} mode" >&2
        exit 1
      fi
      grep -Fq "unsafe destination parent" "${SANDBOX}/owned-unsafe.err"
      if [[ "${target_state}" == existing ]]; then
        [[ "$(snapshot_tree "${external}")" == "${before}" ]]
      else
        [[ ! -e "${external}" ]]
      fi
      unlink "${WORKTREE_ROOT}/${relative}"
    done
  done
  mv "${held}" "${WORKTREE_ROOT}/${relative}"
done

unlink "${WORKTREE_ROOT}/graphify-out/cache/semantic"
ln -s "${SHARED_ROOT}/.data/offline_cache" "${WORKTREE_ROOT}/graphify-out/cache/semantic"
if run_setup "${WORKTREE_ROOT}" >"${SANDBOX}/wrong-semantic.out" 2>"${SANDBOX}/wrong-semantic.err"; then
  echo "setup unexpectedly replaced a wrong semantic cache link" >&2
  exit 1
fi
grep -Fq "semantic cache points somewhere else" "${SANDBOX}/wrong-semantic.err"
[[ "$(readlink -f "${WORKTREE_ROOT}/graphify-out/cache/semantic")" == "${SHARED_ROOT}/.data/offline_cache" ]]
unlink "${WORKTREE_ROOT}/graphify-out/cache/semantic"
ln -s "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic" "${WORKTREE_ROOT}/graphify-out/cache/semantic"

unlink "${WORKTREE_ROOT}/graphify-out/cache/semantic"
if run_setup "${WORKTREE_ROOT}" --check >"${SANDBOX}/missing-semantic.out" 2>"${SANDBOX}/missing-semantic.err"; then
  echo "--check unexpectedly accepted a missing semantic cache link" >&2
  exit 1
fi
grep -Fq "semantic cache is not linked" "${SANDBOX}/missing-semantic.err"
ln -s "${SHARED_ROOT}/.data/graphify-semantic-cache/semantic" "${WORKTREE_ROOT}/graphify-out/cache/semantic"

unlink "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep"
mkdir "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep"
touch "${WORKTREE_ROOT}/graphify-out/cache/semantic-deep/keep"
if run_setup "${WORKTREE_ROOT}" >"${SANDBOX}/semantic-collision.out" 2>"${SANDBOX}/semantic-collision.err"; then
  echo "setup unexpectedly replaced a semantic-deep cache collision" >&2
  exit 1
fi
grep -Fq "semantic-deep cache is not linked" "${SANDBOX}/semantic-collision.err"
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
grep -Fq "semantic-deep cache is not linked" "${SANDBOX}/semantic-deep-file.err"
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
