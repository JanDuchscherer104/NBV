#!/usr/bin/env python3
"""Hermetic contract and immutability tests for the agent-status command."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "agent_status.py"
sys.path.insert(0, str(ROOT / "scripts"))
from agent_status import GitBoundary, _graphify  # noqa: E402


def filesystem_snapshot(paths: list[Path]) -> dict[str, tuple[Any, ...]]:
    """Capture repository and Git-directory metadata without invoking Git."""
    snapshot: dict[str, tuple[Any, ...]] = {}
    for base in paths:
        base = base.resolve()
        if not base.exists() and not base.is_symlink():
            snapshot[str(base)] = ("missing",)
            continue
        pending = [base]
        while pending:
            path = pending.pop()
            info = path.lstat()
            mode = stat.S_IFMT(info.st_mode)
            key = str(path)
            common = (
                mode,
                stat.S_IMODE(info.st_mode),
                info.st_size,
                info.st_mtime_ns,
                info.st_ctime_ns,
            )
            if stat.S_ISREG(mode):
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                snapshot[key] = (*common, digest)
            elif stat.S_ISLNK(mode):
                snapshot[key] = (*common, os.readlink(path))
            elif stat.S_ISDIR(mode):
                snapshot[key] = common
                pending.extend(path.iterdir())
            else:
                snapshot[key] = common
    return snapshot


def render(path: Path) -> str:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--path", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


class AgentStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="aria-agent-status-")
        self.root = Path(self.temp_dir.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Agent Status Test")
        (self.root / "README.md").write_text("seed\n", encoding="utf-8")
        self.git("add", "README.md")
        self.git("commit", "-qm", "seed")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def git(self, *args: str, cwd: Path | None = None) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd or self.root,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def invoke(
        self,
        path: Path,
        *args: str,
        env: dict[str, str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json", "--path", str(path), *args],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        return result, json.loads(result.stdout)

    def assert_immutable(
        self,
        path: Path,
        common: Path,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        before = filesystem_snapshot([path, common])
        first_result, first = self.invoke(path, env=env)
        second_result, second = self.invoke(path, env=env)
        self.assertEqual(first_result.returncode, 0, first_result.stderr)
        self.assertEqual(second_result.returncode, 0, second_result.stderr)
        self.assertEqual(first, second)
        self.assertEqual(before, filesystem_snapshot([path, common]))
        return first

    def assert_shape(self, envelope: dict[str, Any]) -> None:
        self.assertEqual(set(envelope), {"schema_version", "ok", "result", "error"})
        self.assertEqual(envelope["schema_version"], 1)
        self.assertIsInstance(envelope["ok"], bool)
        if envelope["ok"]:
            self.assertIsNone(envelope["error"])
            result = envelope["result"]
            self.assertIsInstance(result, dict)
            assert isinstance(result, dict)
            self.assertEqual(set(result), {"repository", "readiness", "graphify"})
            repository = result["repository"]
            self.assertEqual(
                set(repository),
                {
                    "root",
                    "bare",
                    "kind",
                    "registration",
                    "branch",
                    "branch_state",
                    "symbolic_head",
                    "head",
                    "head_state",
                    "upstream",
                    "dirty",
                    "git_directory",
                    "common_git_directory",
                    "warning",
                },
            )
            self.assertIsInstance(repository["root"], str)
            self.assertIsInstance(repository["bare"], bool)
            self.assert_status_shape(
                repository["registration"],
                {"state", "details", "next_action", "worktrees"},
            )
            self.assert_status_shape(
                repository["upstream"],
                {"state", "details", "next_action", "name", "ahead", "behind"},
            )
            self.assert_status_shape(
                repository["dirty"], {"state", "details", "next_action"}
            )
            self.assertEqual(set(result["readiness"]), {"runtime", "submodules"})
            self.assert_status_shape(
                result["readiness"]["runtime"],
                {"state", "details", "next_action", "path"},
            )
            self.assert_status_shape(
                result["readiness"]["submodules"], {"state", "details", "next_action"}
            )
            self.assert_status_shape(
                result["graphify"], {"state", "details", "next_action"}
            )
        else:
            self.assertIsNone(envelope["result"])
            error = envelope["error"]
            self.assertEqual(set(error), {"code", "message", "details", "next_action"})
            self.assertIsInstance(error["details"], list)

    def assert_status_shape(self, value: Any, keys: set[str]) -> None:
        self.assertIsInstance(value, dict)
        assert isinstance(value, dict)
        self.assertEqual(set(value), keys)
        self.assertIsInstance(value["state"], str)
        self.assertIsInstance(value["details"], list)
        self.assertTrue(all(isinstance(item, str) for item in value["details"]))
        self.assertTrue(
            value["next_action"] is None or isinstance(value["next_action"], str)
        )

    def test_topology_primary_linked_standalone_and_bare(self) -> None:
        linked = self.root.parent / f"{self.root.name}-linked"
        self.git("worktree", "add", "-q", "-b", "linked", str(linked))
        try:
            primary = self.assert_immutable(self.root, self.root / ".git")
            linked_payload = self.assert_immutable(linked, self.root / ".git")
            self.assertEqual(primary["result"]["repository"]["kind"], "primary")
            self.assertEqual(linked_payload["result"]["repository"]["kind"], "linked")
        finally:
            self.git("worktree", "remove", "-f", str(linked))

        standalone = self.root.parent / f"{self.root.name}-standalone"
        self.git("clone", "-q", str(self.root), str(standalone))
        payload = self.assert_immutable(standalone, standalone / ".git")
        self.assertEqual(payload["result"]["repository"]["kind"], "standalone")

        bare = self.root.parent / f"{self.root.name}-bare.git"
        self.git("clone", "--bare", "-q", str(self.root), str(bare))
        payload = self.assert_immutable(bare, bare)
        result, _ = self.invoke(bare)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["result"]["repository"]["kind"], "bare")
        self.assertIsNotNone(payload["result"]["repository"]["symbolic_head"])
        self.assertEqual(
            payload["result"]["repository"]["upstream"]["state"], "not-applicable"
        )
        self.assertIn(
            "must not be used as current source",
            payload["result"]["repository"]["warning"],
        )
        self.assertIn("no working files", render(bare))

    def test_moved_linked_worktree_is_unregistered_without_repair(self) -> None:
        linked = self.root.parent / f"{self.root.name}-linked"
        moved = self.root.parent / f"{self.root.name}-moved"
        self.git("worktree", "add", "-q", "-b", "linked", str(linked))
        linked.rename(moved)
        payload = self.assert_immutable(moved, self.root / ".git")
        repository = payload["result"]["repository"]
        self.assertEqual(repository["kind"], "linked")
        self.assertEqual(repository["registration"]["state"], "unregistered")
        self.assertEqual(
            repository["registration"]["next_action"],
            f"git -C {moved} worktree repair {moved}",
        )
        self.assertIn(
            f"Next action: git -C {moved} worktree repair {moved}", render(moved)
        )
        self.assert_shape(payload)

    def test_unborn_repo_is_success_with_fixed_states(self) -> None:
        unborn = self.root.parent / f"{self.root.name}-unborn"
        unborn.mkdir()
        self.git("init", "-q", "-b", "main", cwd=unborn)
        result, payload = self.invoke(unborn)
        self.assertEqual(result.returncode, 0, result.stderr)
        repository = payload["result"]["repository"]
        self.assertEqual(repository["branch_state"], "unborn")
        self.assertEqual(repository["head_state"], "unborn")
        self.assertIsNone(repository["head"])

    def test_detached_dirty_missing_upstream_and_runtime_absent(self) -> None:
        self.git("checkout", "--detach", "-q")
        (self.root / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        (self.root / "README.link").symlink_to("README.md")
        payload = self.assert_immutable(self.root, self.root / ".git")
        repository = payload["result"]["repository"]
        self.assertEqual(repository["branch_state"], "detached")
        self.assertEqual(repository["dirty"]["state"], "dirty")
        self.assertEqual(repository["upstream"]["state"], "unavailable")
        self.assertEqual(
            payload["result"]["readiness"]["runtime"]["state"], "uninitialized"
        )
        self.assertIn("upstream: unavailable", render(self.root))

    def test_nested_path_uses_discovered_checkout_root_for_all_probes(self) -> None:
        nested = self.root / "nested"
        nested.mkdir()
        (self.root / "aria_nbv").mkdir()
        (self.root / "aria_nbv" / "pyproject.toml").write_text(
            "[project]\n", encoding="utf-8"
        )
        scripts = self.root / "scripts"
        scripts.mkdir()
        (scripts / "check_graphify_freshness.py").write_text("# fixture\n", encoding="utf-8")
        (scripts / "build_graphify_projection.py").write_text("# fixture\n", encoding="utf-8")

        payload = self.assert_immutable(nested, self.root / ".git")

        result = payload["result"]
        assert result is not None
        self.assertEqual(result["repository"]["root"], str(self.root))
        self.assertEqual(result["repository"]["kind"], "standalone")
        self.assertEqual(
            result["readiness"]["runtime"]["path"],
            str(self.root / "aria_nbv" / ".venv" / "bin" / "python"),
        )
        self.assertEqual(
            result["readiness"]["runtime"]["next_action"],
            f"cd {self.root / 'aria_nbv'} && uv sync --extra dev",
        )
        self.assertIn(f"cd {self.root}", result["graphify"]["next_action"])

    def test_broken_executable_runtime_is_not_healthy(self) -> None:
        runtime = self.root / "aria_nbv" / ".venv" / "bin" / "python"
        runtime.parent.mkdir(parents=True)
        runtime.write_text("#!/missing/python\n", encoding="utf-8")
        runtime.chmod(0o755)

        payload = self.assert_immutable(self.root, self.root / ".git")

        runtime_status = payload["result"]["readiness"]["runtime"]
        self.assertEqual(runtime_status["state"], "unusable")
        self.assertTrue(any("could not start" in detail for detail in runtime_status["details"]))

    def test_missing_upstream_does_not_suggest_invalid_repair(self) -> None:
        payload = self.assert_immutable(self.root, self.root / ".git")
        upstream = payload["result"]["repository"]["upstream"]
        self.assertEqual(upstream["state"], "unavailable")
        self.assertEqual(upstream["next_action"], f"git -C {self.root} remote -v")
        self.assertNotIn("set-upstream", upstream["next_action"])

    def test_tracked_file_mtime_only_does_not_become_dirty(self) -> None:
        source = self.root / "README.md"
        info = source.stat()
        os.utime(source, ns=(info.st_atime_ns, info.st_mtime_ns + 1_000_000))
        payload = self.assert_immutable(self.root, self.root / ".git")
        self.assertEqual(payload["result"]["repository"]["dirty"]["state"], "clean")

    def test_corrupt_index_is_unavailable_but_not_command_failure(self) -> None:
        (self.root / ".git" / "index").write_bytes(b"corrupt index")
        payload = self.assert_immutable(self.root, self.root / ".git")
        self.assertEqual(
            payload["result"]["repository"]["dirty"]["state"], "unavailable"
        )
        self.assertIsInstance(payload["result"]["repository"]["dirty"]["details"], list)

    def test_git_configuration_cannot_run_fsmonitor_or_untracked_cache(self) -> None:
        local_marker = self.root / "local-fsmonitor-invoked"
        global_marker = self.root / "global-fsmonitor-invoked"
        local_hook = self.root / "local-fsmonitor-hook.py"
        local_hook.write_text(
            "#!/usr/bin/env python3\n"
            "from pathlib import Path\n"
            "import sys\n"
            f"Path({str(local_marker)!r}).write_text('hook\\n')\n"
            "sys.stdin.read()\n"
            "print('0')\n",
            encoding="utf-8",
        )
        local_hook.chmod(0o755)
        self.git("config", "core.fsmonitor", str(local_hook))
        self.git("config", "core.untrackedCache", "true")
        positive_env = os.environ.copy()
        for key in list(positive_env):
            if key.startswith("GIT_CONFIG_"):
                positive_env.pop(key)
        positive_env["GIT_CONFIG_NOSYSTEM"] = "1"
        positive_env["GIT_CONFIG_GLOBAL"] = os.devnull
        positive_env["GIT_OPTIONAL_LOCKS"] = "0"
        positive = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
            env=positive_env,
        )
        self.assertEqual(positive.returncode, 0)
        self.assertTrue(local_marker.is_file())
        local_marker.unlink()
        local_payload = self.assert_immutable(
            self.root, self.root / ".git", env=positive_env
        )
        self.assertTrue(local_payload["ok"])
        self.assertFalse(local_marker.exists())

        self.git("config", "--unset", "core.fsmonitor")
        global_hook = self.root / "global-fsmonitor-hook.py"
        global_hook.write_text(
            "#!/usr/bin/env python3\n"
            "from pathlib import Path\n"
            "import sys\n"
            f"Path({str(global_marker)!r}).write_text('hook\\n')\n"
            "sys.stdin.read()\n"
            "print('0')\n",
            encoding="utf-8",
        )
        global_hook.chmod(0o755)
        global_config = self.root.parent / f"{self.root.name}-global-config"
        global_config.write_text(
            "[core]\n\tfsmonitor = " + str(global_hook) + "\n",
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["GIT_CONFIG_GLOBAL"] = str(global_config)
        payload = self.assert_immutable(self.root, self.root / ".git", env=env)
        self.assertTrue(payload["ok"])
        self.assertFalse(global_marker.exists())
        boundary = GitBoundary(self.root)
        self.assertEqual(boundary.env["GIT_OPTIONAL_LOCKS"], "0")
        self.assertEqual(boundary.env["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(boundary.env["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(boundary.env["GIT_CONFIG_VALUE_0"], "false")
        self.assertEqual(boundary.env["GIT_CONFIG_VALUE_1"], "false")

    def test_ambient_git_variables_cannot_redirect_identity(self) -> None:
        other = self.root.parent / f"{self.root.name}-other"
        self.git("init", "-q", str(other))
        env = os.environ.copy()
        for name in (
            "GIT_DIR",
            "GIT_WORK_TREE",
            "GIT_COMMON_DIR",
            "GIT_INDEX_FILE",
            "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "GIT_NAMESPACE",
            "GIT_CEILING_DIRECTORIES",
            "GIT_DISCOVERY_ACROSS_FILESYSTEM",
        ):
            env[name] = str(other)
        env["GIT_OPTIONAL_LOCKS"] = "1"
        result, payload = self.invoke(self.root, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            payload["result"]["repository"]["root"], str(self.root.resolve())
        )

    def test_unusable_graphify_and_exact_shape(self) -> None:
        (self.root / "graphify-out").mkdir()
        (self.root / "graphify-input").mkdir()
        (self.root / "graphify-input" / "index.md").write_text(
            "broken\n", encoding="utf-8"
        )
        (self.root / "graphify-out" / "graph.json").write_text("{}\n", encoding="utf-8")
        result, payload = self.invoke(self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["result"]["graphify"]["state"], "unusable")
        self.assertIsNone(payload["result"]["graphify"]["next_action"])
        self.assertTrue(
            any(
                detail.startswith("Graphify checker next_action:")
                for detail in payload["result"]["graphify"]["details"]
            )
        )
        self.assert_shape(payload)

    def test_primary_graphify_action_builds_then_refreshes(self) -> None:
        scripts = self.root / "scripts"
        scripts.mkdir()
        (scripts / "check_graphify_freshness.py").write_text("# fixture\n", encoding="utf-8")
        (scripts / "build_graphify_projection.py").write_text("# fixture\n", encoding="utf-8")

        graphify = _graphify(GitBoundary(self.root), bare=False, kind="standalone")

        self.assertEqual(graphify["state"], "unavailable")
        self.assertEqual(
            graphify["next_action"],
            f"cd {self.root} && python3 scripts/build_graphify_projection.py "
            '--output graphify-input --aria-code-ref "$(git rev-parse HEAD)" '
            "&& graphify . --update",
        )

    def test_healthy_graphify_preserves_owner_evidence_without_action(self) -> None:
        (self.root / "graphify-out").mkdir()
        (self.root / "graphify-input").mkdir()
        (self.root / "graphify-input" / "index.md").write_text(
            "index\n", encoding="utf-8"
        )
        (self.root / "graphify-out" / "graph.json").write_text("{}\n", encoding="utf-8")
        checker = subprocess.CompletedProcess(
            [], 0, '{"state":"fresh","reasons":[],"next_action":"query prose"}', ""
        )
        with patch("agent_status.subprocess.run", return_value=checker):
            graphify = _graphify(GitBoundary(self.root), bare=False, kind="standalone")
        self.assertEqual(graphify["state"], "healthy")
        self.assertIsNone(graphify["next_action"])
        self.assertIn("Graphify checker next_action: query prose", graphify["details"])

    def test_graphify_rejects_non_object_json_payload(self) -> None:
        (self.root / "graphify-input").mkdir()
        (self.root / "graphify-input" / "index.md").write_text(
            "index\n", encoding="utf-8"
        )
        (self.root / "graphify-out").mkdir()
        (self.root / "graphify-out" / "graph.json").write_text("{}\n", encoding="utf-8")
        checker = subprocess.CompletedProcess([], 1, "[]", "checker warning")
        with patch("agent_status.subprocess.run", return_value=checker):
            graphify = _graphify(GitBoundary(self.root), bare=False, kind="standalone")
        self.assertEqual(graphify["state"], "unusable")
        self.assertIsNone(graphify["next_action"])
        self.assertIn(
            "Graphify checker JSON payload is not an object", graphify["details"]
        )
        self.assertIn("Graphify checker exit status: 1", graphify["details"])
        self.assertIn("Graphify checker stdout: []", graphify["details"])
        self.assertIn("Graphify checker stderr: checker warning", graphify["details"])

    def test_graphify_rejects_fresh_state_with_nonzero_exit(self) -> None:
        (self.root / "graphify-input").mkdir()
        (self.root / "graphify-input" / "index.md").write_text(
            "index\n", encoding="utf-8"
        )
        (self.root / "graphify-out").mkdir()
        (self.root / "graphify-out" / "graph.json").write_text("{}\n", encoding="utf-8")
        stdout = (
            '{"state":"fresh","reasons":["owner reason"],"next_action":"owner prose"}'
        )
        checker = subprocess.CompletedProcess([], 9, stdout, "checker failure")
        with patch("agent_status.subprocess.run", return_value=checker):
            graphify = _graphify(GitBoundary(self.root), bare=False, kind="standalone")
        self.assertEqual(graphify["state"], "unusable")
        self.assertIsNone(graphify["next_action"])
        self.assertIn("Graphify checker state: fresh", graphify["details"])
        self.assertIn("owner reason", graphify["details"])
        self.assertIn("Graphify checker next_action: owner prose", graphify["details"])
        self.assertIn(
            "Graphify checker state 'fresh' requires exit status 0, got 9",
            graphify["details"],
        )
        self.assertIn("Graphify checker exit status: 9", graphify["details"])
        self.assertIn(f"Graphify checker stdout: {stdout}", graphify["details"])
        self.assertIn("Graphify checker stderr: checker failure", graphify["details"])

    def test_graphify_rejects_unknown_checker_state(self) -> None:
        (self.root / "graphify-input").mkdir()
        (self.root / "graphify-input" / "index.md").write_text(
            "index\n", encoding="utf-8"
        )
        (self.root / "graphify-out").mkdir()
        (self.root / "graphify-out" / "graph.json").write_text("{}\n", encoding="utf-8")
        stdout = (
            '{"state":"unknown","reasons":["owner reason"],"next_action":"owner prose"}'
        )
        checker = subprocess.CompletedProcess([], 1, stdout, "checker warning")
        with patch("agent_status.subprocess.run", return_value=checker):
            graphify = _graphify(GitBoundary(self.root), bare=False, kind="standalone")
        self.assertEqual(graphify["state"], "unusable")
        self.assertIsNone(graphify["next_action"])
        self.assertIn("Graphify checker state: unknown", graphify["details"])
        self.assertIn("owner reason", graphify["details"])
        self.assertIn("Graphify checker next_action: owner prose", graphify["details"])
        self.assertIn("Graphify checker returned an unknown state", graphify["details"])
        self.assertIn("Graphify checker exit status: 1", graphify["details"])
        self.assertIn(f"Graphify checker stdout: {stdout}", graphify["details"])
        self.assertIn("Graphify checker stderr: checker warning", graphify["details"])

    def test_graphify_accepts_usable_stale_with_exit_one(self) -> None:
        (self.root / "graphify-input").mkdir()
        (self.root / "graphify-input" / "index.md").write_text(
            "index\n", encoding="utf-8"
        )
        (self.root / "graphify-out").mkdir()
        (self.root / "graphify-out" / "graph.json").write_text("{}\n", encoding="utf-8")
        checker = subprocess.CompletedProcess(
            [],
            1,
            '{"state":"usable-stale","reasons":["stale reason"],"next_action":"refresh prose"}',
            "",
        )
        with patch("agent_status.subprocess.run", return_value=checker):
            graphify = _graphify(GitBoundary(self.root), bare=False, kind="standalone")
        self.assertEqual(graphify["state"], "stale")
        self.assertIsNone(graphify["next_action"])
        self.assertIn("Graphify checker state: usable-stale", graphify["details"])
        self.assertIn("stale reason", graphify["details"])
        self.assertIn(
            "Graphify checker next_action: refresh prose", graphify["details"]
        )

    def test_linked_aria_existing_graphify_seed_has_no_generic_action(self) -> None:
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "check_graphify_freshness.py").write_text(
            "# fixture\n", encoding="utf-8"
        )
        (self.root / "scripts" / "setup_worktree_env.sh").write_text(
            "# fixture\n", encoding="utf-8"
        )
        (self.root / "scripts" / "build_graphify_projection.py").write_text(
            "# fixture\n", encoding="utf-8"
        )
        (self.root / "graphify-input").mkdir()
        (self.root / "graphify-input" / "index.md").write_text(
            "index\n", encoding="utf-8"
        )
        (self.root / "graphify-out").mkdir()
        (self.root / "graphify-out" / "graph.json").write_text("{}\n", encoding="utf-8")
        (self.root / "graphify-out" / ".aria-worktree-seed.json").write_text(
            "{}\n", encoding="utf-8"
        )
        checker = subprocess.CompletedProcess(
            [],
            1,
            '{"state":"unusable","reasons":["fixture reason"],"next_action":"repair prose"}',
            "",
        )
        with patch("agent_status.subprocess.run", return_value=checker):
            graphify = _graphify(GitBoundary(self.root), bare=False, kind="linked")
        self.assertEqual(graphify["state"], "unusable")
        self.assertEqual(graphify["next_action"], f"cd {self.root} && graphify . --update")
        self.assertIn("Graphify checker state: unusable", graphify["details"])
        self.assertIn("fixture reason", graphify["details"])
        self.assertIn("Graphify checker next_action: repair prose", graphify["details"])

    def test_json_error_has_the_same_envelope(self) -> None:
        result, payload = self.invoke(self.root.parent / "does-not-exist")
        self.assertEqual(result.returncode, 1)
        self.assert_shape(payload)
        self.assertFalse(payload["ok"])


if __name__ == "__main__":
    unittest.main()
