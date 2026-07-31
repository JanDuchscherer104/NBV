#!/bin/sh
set -eu

ROOT=$(git rev-parse --show-toplevel)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/aria-codex-hooks.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
REPO="$TMP/repo"
SESSIONS="$TMP/sessions"
THREAD="019f-hook-test"
SCOPE_START="2026-07-30T20:00:00Z"

git init -q "$REPO"
git -C "$REPO" config user.email hooks@example.invalid
git -C "$REPO" config user.name "Hook Tests"
mkdir -p "$REPO/scripts/git_hooks" "$SESSIONS/2026/07/30"
cp "$ROOT/scripts/codex_transcript_extract.py" "$REPO/scripts/"
cp "$ROOT/scripts/codex_transcript_provenance.py" "$REPO/scripts/"
cp "$ROOT/scripts/codex_commit.sh" "$REPO/scripts/"
cp "$ROOT/scripts/git_hooks/pre-commit" "$REPO/scripts/git_hooks/"
cp "$ROOT/scripts/git_hooks/prepare-commit-msg" "$REPO/scripts/git_hooks/"
cp "$ROOT/scripts/git_hooks/commit-msg" "$REPO/scripts/git_hooks/"
cat >"$REPO/scripts/git_hooks/post-commit" <<'EOF'
#!/bin/sh
exit 0
EOF
chmod +x "$REPO/scripts/codex_commit.sh" "$REPO/scripts/git_hooks/"*

printf 'base\n' >"$REPO/base.txt"
git -C "$REPO" add base.txt
git -C "$REPO" commit -qm base
BASE=$(git -C "$REPO" rev-parse HEAD)
DEFAULT_BRANCH=$(git -C "$REPO" branch --show-current)
git -C "$REPO" config core.hooksPath scripts/git_hooks

printf 'human\n' >"$REPO/human.txt"
git -C "$REPO" add human.txt
git -C "$REPO" commit -qm human
test -z "$(git -C "$REPO" show -s --format=%B HEAD | grep '^Codex-Transcript:' || true)"

SESSION="$SESSIONS/2026/07/30/rollout-$THREAD.jsonl"
printf '{"timestamp":"2026-07-30T20:00:00Z","type":"session_meta","payload":{"id":"%s","timestamp":"2026-07-30T20:00:00Z","cwd":"%s"}}\n' "$THREAD" "$REPO" >"$SESSION"
printf '%s\n' '{"timestamp":"2026-07-30T20:00:01Z","type":"response_item","payload":{"type":"message","role":"user","content":[{"text":"Commit the scoped change"}]}}' >>"$SESSION"
printf '%s\n' '{"timestamp":"2026-07-30T20:00:02Z","type":"response_item","payload":{"type":"message","role":"assistant","content":[{"text":"Implemented and verified"}]}}' >>"$SESSION"

printf 'codex\n' >"$REPO/codex.txt"
git -C "$REPO" add codex.txt
if (
  cd "$REPO"
  CODEX_THREAD_ID="$THREAD" CODEX_SESSIONS_ROOT="$SESSIONS" \
    ./scripts/codex_commit.sh -qm codex
); then
  echo "Codex wrapper accepted a missing transcript scope" >&2
  exit 1
fi
(
  cd "$REPO"
  CODEX_THREAD_ID="$THREAD" CODEX_TRANSCRIPT_SCOPE_START="$SCOPE_START" \
    CODEX_SESSIONS_ROOT="$SESSIONS" ./scripts/codex_commit.sh -qm codex
)

test "$(git -C "$REPO" show -s --format=%B HEAD | grep -c '^Codex-Transcript:')" -eq 1
test "$(git -C "$REPO" show --format= --name-only HEAD | grep -c '^.agents/memory/transcripts/commits/')" -eq 1
python3 "$REPO/scripts/codex_transcript_provenance.py" validate-range --repo "$REPO" "$BASE" HEAD
python3 "$REPO/scripts/codex_transcript_provenance.py" check-hooks --repo "$REPO"
test ! -f "$(git -C "$REPO" rev-parse --absolute-git-dir)/aria-codex-transcript-state.json"

# An unchanged session still yields a distinct artifact because pre-commit HEAD
# participates in the deterministic snapshot identity.
printf 'second\n' >"$REPO/second.txt"
git -C "$REPO" add second.txt
(
  cd "$REPO"
  CODEX_THREAD_ID="$THREAD" CODEX_TRANSCRIPT_SCOPE_START="$SCOPE_START" \
    CODEX_SESSIONS_ROOT="$SESSIONS" ./scripts/codex_commit.sh -m second
)
test "$(git -C "$REPO" log -2 --format=%B | grep -c '^Codex-Transcript:')" -eq 2
test "$(git -C "$REPO" ls-files '.agents/memory/transcripts/commits/**' | wc -l)" -eq 2

# A downstream pre-commit failure clears nonce state and only the generated
# artifact, preserving unrelated staging for a clean retry.
mkdir -p "$TMP/bin"
cat >"$TMP/bin/pre-commit" <<'EOF'
#!/bin/sh
exit 9
EOF
chmod +x "$TMP/bin/pre-commit"
printf 'repos: []\n' >"$REPO/.pre-commit-config.yaml"
printf 'retry\n' >"$REPO/retry.txt"
git -C "$REPO" add .pre-commit-config.yaml retry.txt
if (
  cd "$REPO"
  PATH="$TMP/bin:$PATH" CODEX_THREAD_ID="$THREAD" \
    CODEX_TRANSCRIPT_SCOPE_START="$SCOPE_START" CODEX_SESSIONS_ROOT="$SESSIONS" \
    ./scripts/codex_commit.sh -m retry
); then
  echo "expected composed pre-commit failure" >&2
  exit 1
fi
test ! -f "$(git -C "$REPO" rev-parse --absolute-git-dir)/aria-codex-transcript-state.json"
test -z "$(git -C "$REPO" diff --cached --name-only -- '.agents/memory/transcripts/commits/**')"
test "$(git -C "$REPO" diff --cached --name-only | grep -c '^retry.txt$')" -eq 1
git -C "$REPO" rm -q --cached .pre-commit-config.yaml retry.txt
rm -f "$REPO/.pre-commit-config.yaml" "$REPO/retry.txt"

# Active merges fail in pre-commit before transcript capture mutates the index,
# state, or artifact namespace.
git -C "$REPO" checkout -qb merge-feature
printf 'feature\n' >"$REPO/merge-feature.txt"
git -C "$REPO" add merge-feature.txt
git -C "$REPO" commit -qm 'merge feature'
git -C "$REPO" checkout -q "$DEFAULT_BRANCH"
printf 'main\n' >"$REPO/merge-main.txt"
git -C "$REPO" add merge-main.txt
git -C "$REPO" commit -qm 'merge main'
git -C "$REPO" merge --no-ff --no-commit merge-feature >/dev/null
MERGE_HEAD_BEFORE=$(git -C "$REPO" rev-parse HEAD)
TRANSCRIPTS_BEFORE=$(git -C "$REPO" ls-files '.agents/memory/transcripts/commits/**' | wc -l)
INDEX_BEFORE=$(git -C "$REPO" ls-files --stage)
if (
  cd "$REPO"
  CODEX_THREAD_ID="$THREAD" CODEX_TRANSCRIPT_SCOPE_START="$SCOPE_START" \
    CODEX_SESSIONS_ROOT="$SESSIONS" \
    ./scripts/codex_commit.sh -m 'forbidden merge provenance'
); then
  echo "Codex wrapper committed an active merge" >&2
  exit 1
fi
test "$(git -C "$REPO" rev-parse HEAD)" = "$MERGE_HEAD_BEFORE"
test "$(git -C "$REPO" ls-files '.agents/memory/transcripts/commits/**' | wc -l)" -eq "$TRANSCRIPTS_BEFORE"
test "$(git -C "$REPO" ls-files --stage)" = "$INDEX_BEFORE"
test -f "$(git -C "$REPO" rev-parse --path-format=absolute --git-path MERGE_HEAD)"
test ! -f "$(git -C "$REPO" rev-parse --absolute-git-dir)/aria-codex-transcript-state.json"
git -C "$REPO" merge --abort

# Human opt-in trailers are checked from prepare-commit-msg even when
# commit-msg/pre-commit are bypassed with --no-verify.
NONCE=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
ARTIFACT=$(python3 "$REPO/scripts/codex_transcript_provenance.py" capture \
  --repo "$REPO" --thread-id "$THREAD" --sessions-root "$SESSIONS" \
  --scope-start "$SCOPE_START" \
  --invocation-nonce "$NONCE")
MESSAGE="$TMP/human-message"
printf 'human provenance\n' >"$MESSAGE"
python3 "$REPO/scripts/codex_transcript_provenance.py" prepare-message \
  --repo "$REPO" --invocation-nonce "$NONCE" "$MESSAGE"
python3 "$REPO/scripts/codex_transcript_provenance.py" clear-state \
  --repo "$REPO" --invocation-nonce "$NONCE"
git -C "$REPO" commit --no-verify -q -F "$MESSAGE"
test "$(git -C "$REPO" show --format= --name-only HEAD | grep -c "^$ARTIFACT$")" -eq 1

printf 'invalid\n' >"$REPO/invalid.txt"
git -C "$REPO" add invalid.txt
if git -C "$REPO" commit --no-verify -m 'invalid

Codex-Transcript: .agents/memory/transcripts/commits/missing.json sha256=0000000000000000000000000000000000000000000000000000000000000000'; then
  echo "prepare-commit-msg allowed an invalid human transcript trailer" >&2
  exit 1
fi
