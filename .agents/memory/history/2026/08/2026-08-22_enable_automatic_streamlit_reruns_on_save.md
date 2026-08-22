---
id: 2026-08-22_enable_automatic_streamlit_reruns_on_save
date: 2026-08-22
title: "Enable automatic Streamlit reruns on save"
status: done
topics: []
confidence: high
canonical_updates_needed: []
codex_thread: codex://threads/019fffa4-b85c-7db1-8404-d69c73e6485e
repo_branch: codex/rollout-supervision-inspection-refresh
repo_head: e1945d1f1cd6541cde332ddaa7f3ef0a22878ba5
repo_object_format: sha1
worktree_kind: linked
---

## Task
Make `uv run nbv-st` automatically rerun on source saves when its watcher detects a change.

## Method
Inspected the live Streamlit process, wrapper arguments, installed dependency, and Streamlit configuration contract.

## Findings
The wrapper already selected `server.fileWatcherType=auto` and the live process had an inotify file descriptor, proving watchdog was active. It did not set Streamlit's separate `server.runOnSave` setting, whose default is false. `aria_nbv/aria_nbv/streamlit_app.py` now injects `--server.runOnSave true` unless the CLI or `STREAMLIT_SERVER_RUN_ON_SAVE` explicitly overrides it. The application README documents both defaults and the stable-session opt-out.

## Verification
Passed `uv run --project aria_nbv pytest -q aria_nbv/tests/test_streamlit_entry.py` (7 passed), Ruff format/check, `compileall`, and `git diff --check`.

## Canonical Owner Impact
Streamlit console-entry and user documentation only; no app data, schema, generation, training, or inspection semantics change.
